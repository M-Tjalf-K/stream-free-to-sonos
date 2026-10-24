"""Stateful Sonos topology tests; no real speaker is changed."""
import unittest
from contextlib import ExitStack
import xml.etree.ElementTree as ET
from unittest.mock import patch

from test_host import host


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.groups = [["A", "B"], ["C", "D"]]
        self.ips = {name: "192.168.1." + str(i + 2) for i, name in enumerate("ABCD")}
        self.calls = []
        self.fail_join = False
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(host, "topology", side_effect=lambda ip: self.xml()))
        self.stack.enter_context(patch.object(host, "soap", side_effect=self.soap))
        self.stack.enter_context(patch.object(host, "device", return_value={"name": "Test"}))
        self.stack.enter_context(patch.object(host, "volume", return_value=25))
        self.stack.enter_context(patch.object(host, "remember_devices"))

    def xml(self):
        root = ET.Element("ZoneGroups")
        for names in self.groups:
            group = ET.SubElement(root, "ZoneGroup", Coordinator=names[0])
            for name in names:
                room = ET.SubElement(group, "ZoneGroupMember", UUID=name, ZoneName=name,
                                     Location=f"http://{self.ips[name]}:1400/x")
                if name == "A":
                    # Stereo partner and surround satellite remain bonded to A.
                    ET.SubElement(group, "ZoneGroupMember", UUID="H", Invisible="1",
                                  Location="http://192.168.1.80:1400/x")
                    ET.SubElement(room, "Satellite", UUID="S", Location="http://192.168.1.81:1400/x")
        return root

    def remove(self, name):
        for group in self.groups:
            if name in group:
                group.remove(name)
                if not group:
                    self.groups.remove(group)
                return

    def soap(self, ip, service, action, **values):
        self.calls.append((ip, service, action, values))
        name = next(name for name, address in self.ips.items() if address == ip)
        if action == "BecomeCoordinatorOfStandaloneGroup":
            self.remove(name)
            self.groups.append([name])
        elif action == "SetAVTransportURI":
            if self.fail_join:
                raise RuntimeError("speaker offline")
            self.remove(name)
            target = values["CurrentURI"].removeprefix("x-rincon:")
            next(group for group in self.groups if group[0] == target).append(name)
        else:
            self.fail("Unexpected or bonded-zone action: " + action)
        return ET.Element("result")

    def test_discovery_exposes_rooms_without_bonded_players(self):
        result = host.discover(self.ips["A"])
        self.assertEqual({room["uuid"] for group in result for room in group["members"]}, set("ABCD"))

    def test_add_remove_and_move_a_coordinator_without_its_old_followers(self):
        result = host.set_group(self.ips["A"], [self.ips["A"], self.ips["C"]])
        self.assertIn(["A", "C"], self.groups)
        self.assertIn(["B"], self.groups)
        self.assertIn(["D"], self.groups)
        self.assertEqual(next(group for group in result if group["ip"] == self.ips["A"])["name"], "A + C")
        self.assertTrue(all(ip in self.ips.values() and service == "AVTransport" for ip, service, _, _ in self.calls))

    def test_choose_a_follower_as_main_room(self):
        host.set_group(self.ips["B"], [self.ips["B"], self.ips["C"]])
        self.assertIn(["B", "C"], self.groups)
        self.assertIn(["A"], self.groups)
        self.assertIn(["D"], self.groups)

    def test_dissolve_from_follower_splits_entire_selected_group_only(self):
        host.set_group(self.ips["B"], [self.ips["B"]], dissolve=True)
        self.assertIn(["A"], self.groups)
        self.assertIn(["B"], self.groups)
        self.assertIn(["C", "D"], self.groups)

    def test_unchanged_group_does_not_send_writes(self):
        host.set_group(self.ips["A"], [self.ips["A"], self.ips["B"]])
        self.assertEqual(self.calls, [])

    def test_hidden_unknown_or_missing_main_room_rejected_before_any_write(self):
        for members in [None, "AB", [], [True], [self.ips["B"]],
                        [self.ips["A"], "192.168.1.80"], [self.ips["A"], "192.168.1.81"],
                        [self.ips["A"], "192.168.1.99"], [self.ips["A"], "8.8.8.8"]]:
            with self.subTest(members=members), self.assertRaises(ValueError):
                host.set_group(self.ips["A"], members)
        self.assertEqual(self.calls, [])

    def test_partial_failure_is_reported_instead_of_success(self):
        self.fail_join = True
        with self.assertRaisesRegex(RuntimeError, "groupChangeFailed: speaker offline"):
            host.set_group(self.ips["A"], [self.ips["A"], self.ips["C"]])
        self.assertIn(["C"], self.groups)
        self.assertIn(["A", "B"], self.groups)

    def test_success_requires_confirmed_topology(self):
        ticks = iter(range(100))
        with patch.object(host, "soap", return_value=ET.Element("result")), \
                patch.object(host.time, "monotonic", side_effect=lambda: next(ticks)), \
                patch.object(host.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "groupChangeFailed: groupNotConfirmed"):
                host.set_group(self.ips["A"], [self.ips["A"]])


if __name__ == "__main__":
    unittest.main()
