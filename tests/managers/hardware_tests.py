"""
    SoftLayer.tests.managers.hardware_tests
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :license: MIT, see LICENSE for more details.
"""
import copy

import mock

import SoftLayer
from SoftLayer import fixtures
from SoftLayer import managers
from SoftLayer import testing

MINIMAL_TEST_CREATE_ARGS = {
    'size': 'S1270_8GB_2X1TBSATA_NORAID',
    'hostname': 'unicorn',
    'domain': 'giggles.woo',
    'location': 'wdc01',
    'os': 'UBUNTU_14_64',
    'port_speed': 10,
}


class HardwareTests(testing.TestCase):

    def set_up(self):
        self.hardware = SoftLayer.HardwareManager(self.client)

    def test_init_with_ordering_manager(self):
        ordering_manager = SoftLayer.OrderingManager(self.client)
        mgr = SoftLayer.HardwareManager(self.client, ordering_manager)

        self.assertEqual(mgr.ordering_manager, ordering_manager)

    def test_list_hardware(self):
        # Cast result back to list because list_hardware is now a generator
        results = self.hardware.list_hardware()

        self.assertEqual(results, fixtures.SoftLayer_Account.getHardware)
        self.assert_called_with('SoftLayer_Account', 'getHardware')

    def test_list_hardware_with_filters(self):
        results = self.hardware.list_hardware(
            tags=['tag1', 'tag2'],
            cpus=2,
            memory=1,
            hostname='hostname',
            domain='example.com',
            datacenter='dal05',
            nic_speed=100,
            public_ip='1.2.3.4',
            private_ip='4.3.2.1',
        )

        self.assertEqual(results, fixtures.SoftLayer_Account.getHardware)
        _filter = {
            'hardware': {
                'datacenter': {'name': {'operation': '_= dal05'}},
                'domain': {'operation': '_= example.com'},
                'tagReferences': {
                    'tag': {'name': {
                        'operation': 'in',
                        'options': [
                            {'name': 'data', 'value': ['tag1', 'tag2']}]
                    }}
                },
                'memoryCapacity': {'operation': 1},
                'processorPhysicalCoreAmount': {'operation': 2},
                'hostname': {'operation': '_= hostname'},
                'primaryIpAddress': {'operation': '_= 1.2.3.4'},
                'networkComponents': {'maxSpeed': {'operation': 100}},
                'primaryBackendIpAddress': {'operation': '_= 4.3.2.1'}}
        }
        self.assert_called_with('SoftLayer_Account', 'getHardware',
                                filter=_filter)

    def test_resolve_ids_ip(self):
        _id = self.hardware._get_ids_from_ip('172.16.1.100')
        self.assertEqual(_id, [1000, 1001, 1002, 1003])

        _id = self.hardware._get_ids_from_ip('nope')
        self.assertEqual(_id, [])

        # Now simulate a private IP test
        mock = self.set_mock('SoftLayer_Account', 'getHardware')
        mock.side_effect = [[], [{'id': 99}]]

        _id = self.hardware._get_ids_from_ip('10.0.1.87')

        self.assertEqual(_id, [99])

    def test_resolve_ids_hostname(self):
        _id = self.hardware._get_ids_from_hostname('hardware-test1')
        self.assertEqual(_id, [1000, 1001, 1002, 1003])

    def test_get_hardware(self):
        result = self.hardware.get_hardware(1000)

        self.assertEqual(fixtures.SoftLayer_Hardware_Server.getObject, result)
        self.assert_called_with('SoftLayer_Hardware_Server', 'getObject',
                                identifier=1000)

    def test_reload(self):
        post_uri = 'http://test.sftlyr.ws/test.sh'
        result = self.hardware.reload(1, post_uri=post_uri, ssh_keys=[1701])

        self.assertEqual(result, 'OK')
        self.assert_called_with('SoftLayer_Hardware_Server',
                                'reloadOperatingSystem',
                                args=('FORCE',
                                      {'customProvisionScriptUri': post_uri,
                                       'sshKeyIds': [1701]}),
                                identifier=1)

    def test_get_create_options(self):
        options = self.hardware.get_create_options()

        expected = {
            'extras': [{'key': '1_IPV6_ADDRESS', 'name': '1 IPv6 Address'}],
            'locations': [{'key': 'wdc01', 'name': 'Washington 1'}],
            'operating_systems': [{'key': 'OS_UBUNTU_14_04_LTS_TRUSTY_TAHR_64_BIT',
                                   'name': 'Ubuntu / 14.04-64'}],
            'port_speeds': [{
                'key': '10',
                'name': '10 Mbps Public & Private Network Uplinks'
            }],
            'sizes': [
                {
                    'key': 'S1270_8GB_2X1TBSATA_NORAID',
                    'name': 'Single Xeon 1270, 8GB Ram, 2x1TB SATA disks, Non-RAID'
                },
                {
                    'key': 'DGOLD_6140_384GB_4X960GB_SSD_SED_RAID_10',
                    'name': 'Dual Xeon Gold, 384GB Ram, 4x960GB SSD, RAID 10'
                }
            ]
        }

        self.assertEqual(options, expected)

    def test_get_create_options_package_missing(self):
        packages = self.set_mock('SoftLayer_Product_Package', 'getAllObjects')
        packages.return_value = []

        ex = self.assertRaises(SoftLayer.SoftLayerError, self.hardware.get_create_options)
        self.assertEqual("Package BARE_METAL_SERVER does not exist", str(ex))

    def test_generate_create_dict_no_items(self):
        packages = self.set_mock('SoftLayer_Product_Package', 'getAllObjects')
        packages_copy = copy.deepcopy(
            fixtures.SoftLayer_Product_Package.getAllObjects)
        packages_copy[0]['items'] = []
        packages.return_value = packages_copy

        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               self.hardware._generate_create_dict,
                               location="wdc01")
        self.assertIn("Could not find valid price", str(ex))

    def test_generate_create_dict_no_regions(self):
        packages = self.set_mock('SoftLayer_Product_Package', 'getAllObjects')
        packages_copy = copy.deepcopy(
            fixtures.SoftLayer_Product_Package.getAllObjects)
        packages_copy[0]['regions'] = []
        packages.return_value = packages_copy

        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               self.hardware._generate_create_dict,
                               **MINIMAL_TEST_CREATE_ARGS)
        self.assertIn("Could not find valid location for: 'wdc01'", str(ex))

    def test_generate_create_dict_invalid_size(self):
        args = {
            'size': 'UNKNOWN_SIZE',
            'hostname': 'unicorn',
            'domain': 'giggles.woo',
            'location': 'wdc01',
            'os': 'OS_UBUNTU_14_04_LTS_TRUSTY_TAHR_64_BIT',
            'port_speed': 10,
        }

        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               self.hardware._generate_create_dict, **args)
        self.assertIn("Could not find valid size for: 'UNKNOWN_SIZE'", str(ex))

    def test_generate_create_dict(self):
        args = {
            'size': 'S1270_8GB_2X1TBSATA_NORAID',
            'hostname': 'unicorn',
            'domain': 'giggles.woo',
            'location': 'wdc01',
            'os': 'OS_UBUNTU_14_04_LTS_TRUSTY_TAHR_64_BIT',
            'port_speed': 10,
            'hourly': True,
            'extras': ['1_IPV6_ADDRESS'],
            'post_uri': 'http://example.com/script.php',
            'ssh_keys': [10],
        }

        expected = {
            'hardware': [{
                'domain': 'giggles.woo',
                'hostname': 'unicorn',
            }],
            'location': 'WASHINGTON_DC',
            'packageId': 200,
            'presetId': 64,
            'prices': [{'id': 21},
                       {'id': 420},
                       {'id': 906},
                       {'id': 37650},
                       {'id': 1800},
                       {'id': 272},
                       {'id': 17129}],
            'useHourlyPricing': True,
            'provisionScripts': ['http://example.com/script.php'],
            'sshKeys': [{'sshKeyIds': [10]}],
        }

        data = self.hardware._generate_create_dict(**args)

        self.assertEqual(expected, data)

    @mock.patch('SoftLayer.managers.hardware.HardwareManager'
                '._generate_create_dict')
    def test_verify_order(self, create_dict):
        create_dict.return_value = {'test': 1, 'verify': 1}

        self.hardware.verify_order(test=1, verify=1)

        create_dict.assert_called_once_with(test=1, verify=1)
        self.assert_called_with('SoftLayer_Product_Order', 'verifyOrder',
                                args=({'test': 1, 'verify': 1},))

    @mock.patch('SoftLayer.managers.hardware.HardwareManager'
                '._generate_create_dict')
    def test_place_order(self, create_dict):
        create_dict.return_value = {'test': 1, 'verify': 1}
        self.hardware.place_order(test=1, verify=1)

        create_dict.assert_called_once_with(test=1, verify=1)
        self.assert_called_with('SoftLayer_Product_Order', 'placeOrder',
                                args=({'test': 1, 'verify': 1},))

    def test_cancel_hardware_without_reason(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getObject')
        mock.return_value = {'id': 987, 'billingItem': {'id': 1234},
                             'openCancellationTicket': {'id': 1234}}

        result = self.hardware.cancel_hardware(987)

        self.assertEqual(result, True)
        reasons = self.hardware.get_cancellation_reasons()
        args = (False, False, reasons['unneeded'], '')
        self.assert_called_with('SoftLayer_Billing_Item', 'cancelItem', identifier=1234, args=args)

    def test_cancel_hardware_with_reason_and_comment(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getObject')
        mock.return_value = {'id': 987, 'billingItem': {'id': 1234},
                             'openCancellationTicket': {'id': 1234}}

        result = self.hardware.cancel_hardware(6327, reason='sales', comment='Test Comment')

        self.assertEqual(result, True)
        reasons = self.hardware.get_cancellation_reasons()
        args = (False, False, reasons['sales'], 'Test Comment')
        self.assert_called_with('SoftLayer_Billing_Item', 'cancelItem', identifier=1234, args=args)

    def test_cancel_hardware(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getObject')
        mock.return_value = {'id': 987, 'billingItem': {'id': 6327},
                             'openCancellationTicket': {'id': 4567}}
        result = self.hardware.cancel_hardware(6327)

        self.assertEqual(result, True)
        self.assert_called_with('SoftLayer_Billing_Item', 'cancelItem',
                                identifier=6327, args=(False, False, 'No longer needed', ''))

    def test_cancel_hardware_no_billing_item(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getObject')
        mock.return_value = {'id': 987, 'openCancellationTicket': {'id': 1234}}

        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               self.hardware.cancel_hardware,
                               6327)
        self.assertEqual("Ticket #1234 already exists for this server", str(ex))

    def test_cancel_hardwareno_billing_item_or_ticket(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getObject')
        mock.return_value = {'id': 987}

        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               self.hardware.cancel_hardware,
                               6327)
        self.assertEqual("Cannot locate billing for the server. The server may already be cancelled.", str(ex))

    def test_cancel_hardware_monthly_now(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getObject')
        mock.return_value = {'id': 987, 'billingItem': {'id': 1234},
                             'openCancellationTicket': {'id': 4567},
                             'hourlyBillingFlag': False}
        with self.assertLogs('SoftLayer.managers.hardware', level='INFO') as logs:
            result = self.hardware.cancel_hardware(987, immediate=True)
        # should be 2 infom essages here
        self.assertEqual(len(logs.records), 2)

        self.assertEqual(result, True)
        self.assert_called_with('SoftLayer_Billing_Item', 'cancelItem',
                                identifier=1234, args=(False, False, 'No longer needed', ''))
        cancel_message = "Please reclaim this server ASAP, it is no longer needed. Thankyou."
        self.assert_called_with('SoftLayer_Ticket', 'addUpdate',
                                identifier=4567, args=({'entry': cancel_message},))

    def test_cancel_hardware_monthly_whenever(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getObject')
        mock.return_value = {'id': 987, 'billingItem': {'id': 6327},
                             'openCancellationTicket': {'id': 4567}}

        with self.assertLogs('SoftLayer.managers.hardware', level='INFO') as logs:
            result = self.hardware.cancel_hardware(987, immediate=False)
        # should be 2 infom essages here
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(result, True)
        self.assert_called_with('SoftLayer_Billing_Item', 'cancelItem',
                                identifier=6327, args=(False, False, 'No longer needed', ''))

    def test_cancel_running_transaction(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getObject')
        mock.return_value = {'id': 987, 'billingItem': {'id': 6327},
                             'activeTransaction': {'id': 4567}}
        self.assertRaises(SoftLayer.SoftLayerError,
                          self.hardware.cancel_hardware,
                          12345)

    def test_change_port_speed_public(self):
        self.hardware.change_port_speed(2, True, 100, 'degraded')

        self.assert_called_with('SoftLayer_Hardware_Server',
                                'setPublicNetworkInterfaceSpeed',
                                identifier=2,
                                args=([100, 'degraded'],))

    def test_change_port_speed_private(self):
        self.hardware.change_port_speed(2, False, 10, 'redundant')

        self.assert_called_with('SoftLayer_Hardware_Server',
                                'setPrivateNetworkInterfaceSpeed',
                                identifier=2,
                                args=([10, 'redundant'],))

    def test_edit_meta(self):
        # Test editing user data
        self.hardware.edit(100, userdata='my data')

        self.assert_called_with('SoftLayer_Hardware_Server',
                                'setUserMetadata',
                                args=(['my data'],),
                                identifier=100)

    def test_edit_blank(self):
        # Now test a blank edit
        self.assertTrue(self.hardware.edit, 100)
        self.assertEqual(self.calls(), [])

    def test_edit(self):
        # Finally, test a full edit
        self.hardware.edit(100,
                           hostname='new-host',
                           domain='new.sftlyr.ws',
                           notes='random notes')

        self.assert_called_with('SoftLayer_Hardware_Server',
                                'editObject',
                                args=({
                                    'hostname': 'new-host',
                                    'domain': 'new.sftlyr.ws',
                                    'notes': 'random notes',
                                },),
                                identifier=100)

    def test_rescue(self):
        result = self.hardware.rescue(1234)

        self.assertEqual(result, True)
        self.assert_called_with('SoftLayer_Hardware_Server',
                                'bootToRescueLayer',
                                identifier=1234)

    def test_update_firmware(self):
        result = self.hardware.update_firmware(100)

        self.assertEqual(result, True)
        self.assert_called_with('SoftLayer_Hardware_Server',
                                'createFirmwareUpdateTransaction',
                                identifier=100, args=(1, 1, 1, 1))

    def test_update_firmware_selective(self):
        result = self.hardware.update_firmware(100,
                                               ipmi=False,
                                               hard_drive=False)

        self.assertEqual(result, True)
        self.assert_called_with('SoftLayer_Hardware_Server',
                                'createFirmwareUpdateTransaction',
                                identifier=100, args=(0, 1, 1, 0))

    def test_reflash_firmware(self):
        result = self.hardware.reflash_firmware(100)

        self.assertEqual(result, True)
        self.assert_called_with('SoftLayer_Hardware_Server',
                                'createFirmwareReflashTransaction',
                                identifier=100, args=(1, 1, 1))

    def test_reflash_firmware_selective(self):
        result = self.hardware.reflash_firmware(100,
                                                raid_controller=False,
                                                bios=False)

        self.assertEqual(result, True)
        self.assert_called_with('SoftLayer_Hardware_Server',
                                'createFirmwareReflashTransaction',
                                identifier=100, args=(1, 0, 0))

    def test_get_tracking_id(self):
        result = self.hardware.get_tracking_id(1234)
        self.assert_called_with('SoftLayer_Hardware_Server', 'getMetricTrackingObjectId')
        self.assertEqual(result, 1000)

    def test_get_bandwidth_data(self):
        result = self.hardware.get_bandwidth_data(1234, '2019-01-01', '2019-02-01', 'public', 1000)
        self.assert_called_with('SoftLayer_Metric_Tracking_Object',
                                'getBandwidthData',
                                args=('2019-01-01', '2019-02-01', 'public', 1000),
                                identifier=1000)
        self.assertEqual(result[0]['type'], 'cpu0')

    def test_get_bandwidth_allocation(self):
        result = self.hardware.get_bandwidth_allocation(1234)
        self.assert_called_with('SoftLayer_Hardware_Server', 'getBandwidthAllotmentDetail', identifier=1234)
        self.assert_called_with('SoftLayer_Hardware_Server', 'getBillingCycleBandwidthUsage', identifier=1234)
        self.assertEqual(result['allotment']['amount'], '250')
        self.assertEqual(result['usage'][0]['amountIn'], '.448')

    def test_get_bandwidth_allocation_with_allotment(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getBandwidthAllotmentDetail')
        mock.return_value = {
            "allocationId": 11111,
            "id": 22222,
            "allocation": {
                "amount": "2000"
            }
        }

        result = self.hardware.get_bandwidth_allocation(1234)

        self.assertEqual(2000, int(result['allotment']['amount']))

    def test_get_bandwidth_allocation_no_allotment(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getBandwidthAllotmentDetail')
        mock.return_value = None

        result = self.hardware.get_bandwidth_allocation(1234)

        self.assertEqual(None, result['allotment'])

    def test_get_storage_iscsi_details(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getAttachedNetworkStorages')
        mock.return_value = [
            {
                "accountId": 11111,
                "capacityGb": 12000,
                "id": 3777123,
                "nasType": "ISCSI",
                "username": "SL02SEL31111-9",
            }
        ]

        result = self.hardware.get_storage_details(1234, 'ISCSI')

        self.assertEqual([{
            "accountId": 11111,
            "capacityGb": 12000,
            "id": 3777123,
            "nasType": "ISCSI",
            "username": "SL02SEL31111-9",
        }], result)

    def test_get_storage_iscsi_empty_details(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getAttachedNetworkStorages')
        mock.return_value = []

        result = self.hardware.get_storage_details(1234, 'ISCSI')

        self.assertEqual([], result)

    def test_get_storage_nas_details(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getAttachedNetworkStorages')
        mock.return_value = [
            {
                "accountId": 11111,
                "capacityGb": 12000,
                "id": 3777111,
                "nasType": "NAS",
                "username": "SL02SEL32222-9",
            }
        ]

        result = self.hardware.get_storage_details(1234, 'NAS')

        self.assertEqual([{
            "accountId": 11111,
            "capacityGb": 12000,
            "id": 3777111,
            "nasType": "NAS",
            "username": "SL02SEL32222-9",
        }], result)

    def test_get_storage_nas_empty_details(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getAttachedNetworkStorages')
        mock.return_value = []

        result = self.hardware.get_storage_details(1234, 'NAS')

        self.assertEqual([], result)

    def test_get_storage_credentials(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getAllowedHost')
        mock.return_value = {
            "accountId": 11111,
            "id": 33333,
            "name": "iqn.2020-03.com.ibm:sl02su11111-v62941551",
            "resourceTableName": "HARDWARE",
            "credential": {
                "accountId": "11111",
                "id": 44444,
                "password": "SjFDCpHrjskfj",
                "username": "SL02SU11111-V62941551"
            }
        }

        result = self.hardware.get_storage_credentials(1234)

        self.assertEqual({
            "accountId": 11111,
            "id": 33333,
            "name": "iqn.2020-03.com.ibm:sl02su11111-v62941551",
            "resourceTableName": "HARDWARE",
            "credential": {
                "accountId": "11111",
                "id": 44444,
                "password": "SjFDCpHrjskfj",
                "username": "SL02SU11111-V62941551"
            }
        }, result)

    def test_get_none_storage_credentials(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getAllowedHost')
        mock.return_value = None

        result = self.hardware.get_storage_credentials(1234)

        self.assertEqual(None, result)

    def test_get_hard_drives(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getHardDrives')
        mock.return_value = [
            {
                "id": 11111,
                "serialNumber": "z1w4sdf",
                "serviceProviderId": 1,
                "hardwareComponentModel": {
                    "capacity": "1000",
                    "description": "SATAIII:2000:8300:Constellation",
                    "id": 111,
                    "manufacturer": "Seagate",
                    "name": "Constellation ES",
                    "hardwareGenericComponentModel": {
                        "capacity": "1000",
                        "units": "GB",
                        "hardwareComponentType": {
                            "id": 1,
                            "keyName": "HARD_DRIVE",
                            "type": "Hard Drive",
                            "typeParentId": 5
                        }
                    }
                }
            }
        ]

        result = self.hardware.get_hard_drives(1234)

        self.assertEqual([
            {
                "id": 11111,
                "serialNumber": "z1w4sdf",
                "serviceProviderId": 1,
                "hardwareComponentModel": {
                    "capacity": "1000",
                    "description": "SATAIII:2000:8300:Constellation",
                    "id": 111,
                    "manufacturer": "Seagate",
                    "name": "Constellation ES",
                    "hardwareGenericComponentModel": {
                        "capacity": "1000",
                        "units": "GB",
                        "hardwareComponentType": {
                            "id": 1,
                            "keyName": "HARD_DRIVE",
                            "type": "Hard Drive",
                            "typeParentId": 5
                        }
                    }
                }
            }
        ], result)

    def test_get_hard_drive_empty(self):
        mock = self.set_mock('SoftLayer_Hardware_Server', 'getHardDrives')
        mock.return_value = []

        result = self.hardware.get_hard_drives(1234)

        self.assertEqual([], result)


class HardwareHelperTests(testing.TestCase):
    def test_get_extra_price_id_no_items(self):
        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               managers.hardware._get_extra_price_id,
                               [], 'test', True, None)
        self.assertEqual("Could not find valid price for extra option, 'test'", str(ex))

    def test_get_extra_price_mismatched(self):
        items = [
            {'keyName': 'TEST', 'prices': [{'id': 1, 'locationGroupId': None, 'recurringFee': 99}]},
            {'keyName': 'TEST', 'prices': [{'id': 2, 'locationGroupId': 55, 'hourlyRecurringFee': 99}]},
            {'keyName': 'TEST', 'prices': [{'id': 3, 'locationGroupId': None, 'hourlyRecurringFee': 99}]},
        ]
        location = {
            'location': {
                'location': {
                    'priceGroups': [
                        {'id': 50},
                        {'id': 51}
                    ]
                }
            }
        }
        result = managers.hardware._get_extra_price_id(items, 'TEST', True, location)
        self.assertEqual(3, result)

    def test_get_bandwidth_price_mismatched(self):
        items = [
            {'itemCategory': {'categoryCode': 'bandwidth'},
             'capacity': 100,
             'prices': [{'id': 1, 'locationGroupId': None, 'hourlyRecurringFee': 99}]
             },
            {'itemCategory': {'categoryCode': 'bandwidth'},
             'capacity': 100,
             'prices': [{'id': 2, 'locationGroupId': 55, 'recurringFee': 99}]
             },
            {'itemCategory': {'categoryCode': 'bandwidth'},
             'capacity': 100,
             'prices': [{'id': 3, 'locationGroupId': None, 'recurringFee': 99}]
             },
        ]
        location = {
            'location': {
                'location': {
                    'priceGroups': [
                        {'id': 50},
                        {'id': 51}
                    ]
                }
            }
        }
        result = managers.hardware._get_bandwidth_price_id(items, False, False, location)
        self.assertEqual(3, result)

    def test_get_os_price_mismatched(self):
        items = [
            {'itemCategory': {'categoryCode': 'os'},
             'keyName': 'OS_TEST',
             'prices': [{'id': 2, 'locationGroupId': 55, 'recurringFee': 99}]
             },
            {'itemCategory': {'categoryCode': 'os'},
             'keyName': 'OS_TEST',
             'prices': [{'id': 3, 'locationGroupId': None, 'recurringFee': 99}]
             },
        ]
        location = {
            'location': {
                'location': {
                    'priceGroups': [
                        {'id': 50},
                        {'id': 51}
                    ]
                }
            }
        }
        result = managers.hardware._get_os_price_id(items, 'OS_TEST', location)
        self.assertEqual(3, result)

    def test_get_default_price_id_item_not_first(self):
        items = [{
            'itemCategory': {'categoryCode': 'unknown', 'id': 325},
            'keyName': 'UNKNOWN',
            'prices': [{'accountRestrictions': [],
                        'currentPriceFlag': '',
                        'hourlyRecurringFee': '10.0',
                        'id': 1245172,
                        'recurringFee': '1.0'}],
        }]
        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               managers.hardware._get_default_price_id,
                               items, 'unknown', True, None)
        self.assertEqual("Could not find valid price for 'unknown' option", str(ex))

    def test_get_default_price_id_no_items(self):
        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               managers.hardware._get_default_price_id,
                               [], 'test', True, None)
        self.assertEqual("Could not find valid price for 'test' option", str(ex))

    def test_get_bandwidth_price_id_no_items(self):
        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               managers.hardware._get_bandwidth_price_id,
                               [], hourly=True, no_public=False)
        self.assertEqual("Could not find valid price for bandwidth option", str(ex))

    def test_get_os_price_id_no_items(self):
        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               managers.hardware._get_os_price_id,
                               [], 'UBUNTU_14_64', None)
        self.assertEqual("Could not find valid price for os: 'UBUNTU_14_64'", str(ex))

    def test_get_port_speed_price_id_no_items(self):
        ex = self.assertRaises(SoftLayer.SoftLayerError,
                               managers.hardware._get_port_speed_price_id,
                               [], 10, True, None)
        self.assertEqual("Could not find valid price for port speed: '10'", str(ex))

    def test_get_port_speed_price_id_mismatch(self):
        items = [
            {'itemCategory': {'categoryCode': 'port_speed'},
             'capacity': 101,
             'attributes': [{'attributeTypeKeyName': 'IS_PRIVATE_NETWORK_ONLY'}],
             'prices': [{'id': 1, 'locationGroupId': None, 'recurringFee': 99}]
             },
            {'itemCategory': {'categoryCode': 'port_speed'},
             'capacity': 100,
             'attributes': [{'attributeTypeKeyName': 'IS_NOT_PRIVATE_NETWORK_ONLY'}],
             'prices': [{'id': 2, 'locationGroupId': 55, 'recurringFee': 99}]
             },
            {'itemCategory': {'categoryCode': 'port_speed'},
             'capacity': 100,
             'attributes': [{'attributeTypeKeyName': 'IS_PRIVATE_NETWORK_ONLY'}, {'attributeTypeKeyName': 'NON_LACP'}],
             'prices': [{'id': 3, 'locationGroupId': 55, 'recurringFee': 99}]
             },
            {'itemCategory': {'categoryCode': 'port_speed'},
             'capacity': 100,
             'attributes': [{'attributeTypeKeyName': 'IS_PRIVATE_NETWORK_ONLY'}],
             'prices': [{'id': 4, 'locationGroupId': 12, 'recurringFee': 99}]
             },
            {'itemCategory': {'categoryCode': 'port_speed'},
             'capacity': 100,
             'attributes': [{'attributeTypeKeyName': 'IS_PRIVATE_NETWORK_ONLY'}],
             'prices': [{'id': 5, 'locationGroupId': None, 'recurringFee': 99}]
             },
        ]
        location = {
            'location': {
                'location': {
                    'priceGroups': [
                        {'id': 50},
                        {'id': 51}
                    ]
                }
            }
        }
        result = managers.hardware._get_port_speed_price_id(items, 100, True, location)
        self.assertEqual(5, result)

    def test_matches_location(self):
        price = {'id': 1, 'locationGroupId': 51, 'recurringFee': 99}
        location = {
            'location': {
                'location': {
                    'priceGroups': [
                        {'id': 50},
                        {'id': 51}
                    ]
                }
            }
        }
        result = managers.hardware._matches_location(price, location)
        self.assertTrue(result)
