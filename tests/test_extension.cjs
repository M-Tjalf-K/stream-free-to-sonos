const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('localization covers native errors and keeps diagnostic details intact', () => {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync('extension/i18n.js', 'utf8'), context);
  const translate = vm.runInContext('SonosI18n.translate', context);
  assert.equal(translate('ready'), 'Ready');
  assert.equal(translate('ready', 'invalid'), 'Ready');
  assert.equal(translate('streaming', 'de'), 'Übertragung läuft');
  assert.equal(translate('Übertragung läuft'), 'Streaming');
  assert.equal(translate('Bitte eine private IPv4-Adresse des Sonos-Geräts eingeben'), 'Enter a private IPv4 address for the Sonos device');
  assert.equal(translate('FFmpeg beendet: encoder failed'), 'FFmpeg exited: encoder failed');
  assert.equal(translate('Audioverbindung unterbrochen (503)'), 'Audio connection interrupted (HTTP 503)');
  assert.equal(translate('Audio connection interrupted (HTTP 503)', 'de'), 'Audioverbindung unterbrochen (HTTP 503)');
  assert.equal(translate('Sonos lehnt Play ab (HTTP 500). UPnP-Einstellung prüfen. code 701'), 'Sonos rejected Play (HTTP 500). Check the UPnP setting. code 701');
  assert.equal(translate('Unknown OS detail: 123', 'de'), 'Unknown OS detail: 123');
});

test('worklet batches stereo PCM, clips, duplicates mono and sends silence', () => {
  let Processor;
  const chunks = [];
  const sandbox = {
    AudioWorkletProcessor: class { constructor() { this.port = {postMessage: data => chunks.push(new Int16Array(data))}; } },
    registerProcessor: (name, type) => { assert.equal(name, 'pcm'); Processor = type; }
  };
  vm.runInNewContext(fs.readFileSync('extension/pcm-worklet.js', 'utf8'), sandbox);
  const processor = new Processor();
  for (let i = 0; i < 75; i++) processor.process([[new Float32Array(128).fill(2)]]);
  assert.equal(chunks.length, 1);
  assert.equal(chunks[0].length, 19200);
  assert.ok(chunks[0].every(value => value === 32767));
  for (let i = 0; i < 75; i++) processor.process([[]]);
  assert.equal(chunks.length, 2);
  assert.ok(chunks[1].every(value => value === 0));
});

test('worker starts helper after capture consent, stops and releases native port', async () => {
  let listener, hasDocument = false, failGroup = false;
  const calls = [];
  const ports = [];
  const chrome = {
    runtime: {
      id: 'test', lastError: undefined,
      onMessage: {addListener: callback => listener = callback},
      connectNative: () => {
        calls.push('connect');
        let onMessage, onDisconnect;
        const port = {
          onMessage: {addListener: callback => onMessage = callback},
          onDisconnect: {addListener: callback => onDisconnect = callback},
          postMessage: message => {
            calls.push(message.type);
            if (message.type === 'set-group' && failGroup) {
              setImmediate(() => onMessage({id:message.id,error:'groupChangeFailed: speaker offline'}));
              return;
            }
            setImmediate(() => onMessage({id: message.id, result: ['discover','set-group'].includes(message.type) ? [{ip:'192.168.1.2',name:'Test',volume:25}] : message.type === 'start' ? {upload:'http://127.0.0.1:1234/pcm',token:'test'} : true}));
          },
          disconnect: () => { calls.push('disconnect'); setImmediate(onDisconnect); }
        };
        ports.push(port);
        return port;
      },
      sendMessage: async message => { calls.push('offscreen-' + message.type); return {ok:true}; }
    },
    tabCapture: {getMediaStreamId: async ({targetTabId}) => { assert.equal(targetTabId, 42); calls.push('capture'); return 'stream-id'; }},
    offscreen: {hasDocument: async () => hasDocument, createDocument: async () => { hasDocument = true; calls.push('document'); }},
    action: {setBadgeText: async () => {}, setBadgeBackgroundColor: async () => {}}
  };
  vm.runInNewContext(fs.readFileSync('extension/worker.js', 'utf8'), {chrome, setTimeout, clearTimeout, Map, Error});
  function send(message) { return new Promise(resolve => listener(message, {id:'test'}, resolve)); }
  assert.equal((await send({type:'devices'})).ok, true);
  assert.equal(calls.at(-1), 'disconnect');
  const grouped = await send({type:'set-group',ip:'192.168.1.2',members:['192.168.1.2'],dissolve:true});
  assert.equal(grouped.ok, true);
  assert.equal(grouped.result.groupBusy, false);
  assert.equal(calls.at(-1), 'disconnect');
  failGroup = true;
  const failedGroup = await send({type:'set-group',ip:'192.168.1.2',members:['192.168.1.2']});
  assert.equal(failedGroup.ok, false);
  const recovered = await send({type:'state'});
  assert.equal(recovered.result.groupBusy, false);
  assert.equal(recovered.result.devices[0].name, 'Test');
  assert.deepEqual(calls.slice(-3), ['set-group','discover','disconnect']);
  const started = await send({type:'start',tabId:42,ip:'192.168.1.2'});
  assert.equal(started.ok, true);
  assert.equal(started.result.active, true);
  assert.ok(calls.indexOf('capture') < calls.indexOf('start'));
  assert.equal((await send({type:'start',tabId:42,ip:'192.168.1.2'})).ok, false);
  const count = calls.filter(call => call === 'set-group').length;
  assert.equal((await send({type:'set-group',ip:'192.168.1.2',members:['192.168.1.2']})).ok, false);
  assert.equal(calls.filter(call => call === 'set-group').length, count);
  const stopped = await send({type:'stop'});
  assert.equal(stopped.result.active, false);
  assert.equal(calls.at(-1), 'disconnect');
});
