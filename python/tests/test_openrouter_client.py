import unittest

from vesper_terminal.ai.openrouter_client import OpenRouterClient
from vesper_terminal.domain.models import CommandAction


class OpenRouterClientTest(unittest.TestCase):
    def test_tool_json_repair_trailing_comma(self) -> None:
        client = OpenRouterClient()
        response = client.chat(
            'tool {"action":"list_directory","args":{"path":"/ext",},"justification":"x","expected_effect":"y",}'
        )
        self.assertIsNotNone(response.command)
        self.assertEqual(CommandAction.LIST_DIRECTORY, response.command.action)
        self.assertEqual('/ext', response.command.args.path)

    def test_model_tool_call_parsing(self) -> None:
        def requester(_api_key, _payload, _timeout):
            return {
                'choices': [
                    {
                        'message': {
                            'tool_calls': [
                                {
                                    'function': {
                                        'name': 'execute_command',
                                        'arguments': '{"action":"get_device_info","args":{},"justification":"check","expected_effect":"status"}',
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

        client = OpenRouterClient(api_key='sk-test', models=['test/model'], requester=requester)
        response = client.chat('check device')
        self.assertIsNotNone(response.command)
        self.assertEqual(CommandAction.GET_DEVICE_INFO, response.command.action)

    def test_model_fallback(self) -> None:
        calls = {'count': 0}

        def requester(_api_key, payload, _timeout):
            calls['count'] += 1
            if payload['model'] == 'bad/model':
                raise RuntimeError('model unavailable')
            return {
                'choices': [
                    {'message': {'content': 'ok from fallback'}}
                ]
            }

        client = OpenRouterClient(
            api_key='sk-test',
            models=['bad/model', 'good/model'],
            requester=requester,
            retries=0,
        )
        response = client.chat('hello')
        self.assertEqual('ok from fallback', response.assistant_text)
        self.assertEqual(2, calls['count'])

    def test_direct_json_without_tool_prefix(self) -> None:
        client = OpenRouterClient()
        response = client.chat('{"action":"get_storage_info","args":{}}')
        self.assertIsNotNone(response.command)
        self.assertEqual(CommandAction.GET_STORAGE_INFO, response.command.action)

    def test_local_ls_fallback_without_api_key(self) -> None:
        client = OpenRouterClient()
        response = client.chat("ls /ext")
        self.assertIsNotNone(response.command)
        self.assertEqual(CommandAction.LIST_DIRECTORY, response.command.action)
        self.assertEqual("/ext", response.command.args.path)

    def test_local_cat_fallback_without_api_key(self) -> None:
        client = OpenRouterClient()
        response = client.chat("cat /ext/info.txt")
        self.assertIsNotNone(response.command)
        self.assertEqual(CommandAction.READ_FILE, response.command.action)
        self.assertEqual("/ext/info.txt", response.command.args.path)


if __name__ == '__main__':
    unittest.main()
