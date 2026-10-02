const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

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
  let listener, hasDocument = false;
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
            setImmediate(() => onMessage({id: message.id, result: message.type === 'discover' ? [{ip:'192.168.1.2',name:'Test',volume:25}] : message.type === 'start' ? {upload:'http://127.0.0.1:1234/pcm',token:'test'} : true}));
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
  const started = await send({type:'start',tabId:42,ip:'192.168.1.2'});
  assert.equal(started.ok, true);
  assert.equal(started.result.active, true);
  assert.ok(calls.indexOf('capture') < calls.indexOf('start'));
  assert.equal((await send({type:'start',tabId:42,ip:'192.168.1.2'})).ok, false);
  const stopped = await send({type:'stop'});
  assert.equal(stopped.result.active, false);
  assert.equal(calls.at(-1), 'disconnect');
});
