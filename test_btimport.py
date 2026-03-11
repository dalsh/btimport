#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>.

import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import io

# Import the functions to test
# Since btimport.py might not be in the path, we can import it directly
import btimport

class TestBtImport(unittest.TestCase):

    def test_format_mac(self):
        self.assertEqual(btimport.format_mac("001a7dda7113"), "00:1A:7D:DA:71:13")
        self.assertEqual(btimport.format_mac("2c7600ddf69c"), "2C:76:00:DD:F6:9C")
        self.assertEqual(btimport.format_mac("ABCDEF012345"), "AB:CD:EF:01:23:45")

    @patch('btimport.run_chntpw_cmd')
    def test_get_adapter_macs(self, mock_run):
        mock_run.return_value = """
Node has 3 subkeys and 0 values
  <001a7dda7113>
  <4845e66504ee>
  <089df440a2e4>
"""
        macs = btimport.get_adapter_macs("/fake/hive")
        self.assertEqual(macs, ["001a7dda7113", "4845e66504ee", "089df440a2e4"])
        mock_run.assert_called_once_with(["cd \\ControlSet001\\Services\\BTHPORT\\Parameters\\Keys", "ls"], "/fake/hive")

    @patch('btimport.run_chntpw_cmd')
    def test_get_keys_for_adapter(self, mock_run):
        # First call to ls
        # Second call to hex for device 1
        # Third call to hex for device 2
        mock_run.side_effect = [
            # ls output
            """
Node has 2 subkeys and 2 values
  16  3 REG_BINARY         <2c7600ddf69c>
  16  3 REG_BINARY         <f4d48858c288>
""",
            # hex 2c7600ddf69c output
            ":00000  33 71 43 8D DC E7 0E BF DC 48 20 DA 60 31 C4 B9 3qC......H .`1..",
            # hex f4d48858c288 output
            ":00000  AA BB CC DD EE FF 00 11 22 33 44 55 66 77 88 99 ...........3DUfw.."
        ]
        
        keys = btimport.get_keys_for_adapter("001a7dda7113", "/fake/hive")
        
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys["2c7600ddf69c"], "3371438DDCE70EBFDC4820DA6031C4B9")
        self.assertEqual(keys["f4d48858c288"], "AABBCCDDEEFF00112233445566778899")

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open, read_data="[General]\nName=Device\n\n[LinkKey]\nKey=ABCDEF0123456789\n")
    def test_update_linux_config_existing_file(self, mock_file, mock_makedirs, mock_exists):
        # Setup: file exists
        mock_exists.return_value = True
        
        success, updated = btimport.update_linux_config("001a7dda7113", "2c7600ddf69c", "FEDCBA9876543210")
        
        self.assertTrue(success)
        self.assertTrue(updated)
        
        # Check if the key was updated in the file
        handle = mock_file()
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn("Key=FEDCBA9876543210", written_content)
        self.assertNotIn("ABCDEF0123456789", written_content)

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open, read_data="[General]\nName=Device\n\n[LinkKey]\nKey=SAME_KEY\n")
    def test_update_linux_config_no_change(self, mock_file, mock_makedirs, mock_exists):
        mock_exists.return_value = True
        
        success, updated = btimport.update_linux_config("001a7dda7113", "2c7600ddf69c", "SAME_KEY")
        
        self.assertTrue(success)
        self.assertFalse(updated)
        # Should not have called write
        mock_file().write.assert_not_called()

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_update_linux_config_new_device(self, mock_file, mock_makedirs, mock_exists):
        # First call for device_path (exists=False)
        # Second call for info_path (exists=False)
        mock_exists.side_effect = [False, False]
        
        success, updated = btimport.update_linux_config("001a7dda7113", "2c7600ddf69c", "NEW_KEY")
        
        self.assertTrue(success)
        self.assertTrue(updated)
        
        mock_makedirs.assert_called_once()
        # Should have called open twice (once for create 'w', once for read 'r', then once for write 'w')
        # Actually in the code:
        # 1. open(info_path, "w") for initial create
        # 2. open(info_path, "r") to read back
        # 3. open(info_path, "w") to update key
        self.assertEqual(mock_file.call_count, 3)

    @patch('btimport.get_adapter_macs')
    @patch('os.getuid')
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.exit')
    def test_version_argument(self, mock_exit, mock_stdout, mock_uid, mock_get_macs):
        # Mocking sys.argv
        with patch('sys.argv', ['btimport.py', '--version']):
            # sys.exit will raise SystemExit in a normal run, 
            # but when mocked it just records the call.
            # We need to make sure the script doesn't continue after sys.exit(0)
            # In btimport.py, the code for version handling ends with sys.exit(0)
            # but since sys.exit is mocked, it continues to the uid check.
            mock_exit.side_effect = SystemExit
            with self.assertRaises(SystemExit):
                btimport.main()
            
        output = mock_stdout.getvalue()
        self.assertIn("btimport version", output)
        self.assertIn("ABSOLUTELY NO WARRANTY", output)
        self.assertTrue("GPLv3" in output or "GNU General Public License v3" in output)
        mock_exit.assert_called_once_with(0)
        # Ensure it didn't continue to the rest of the script
        mock_uid.assert_not_called()
        mock_get_macs.assert_not_called()

if __name__ == '__main__':
    unittest.main()
