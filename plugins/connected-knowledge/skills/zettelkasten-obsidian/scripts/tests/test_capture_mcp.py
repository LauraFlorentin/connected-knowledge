import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class CaptureMCPTests(unittest.TestCase):
    def test_real_stdio_discovery_save_retry_and_no_path_arguments(self):
        async def exercise(root):
            cfg = root/'config.json'
            cfg.write_text(json.dumps({'enabled': True, 'account': 'synthetic',
                                       'spool': str(root/'spool'), 'destination': str(root/'archive')}))
            script = Path(__file__).resolve().parents[1]/'capture_mcp.py'
            params = StdioServerParameters(command=sys.executable, args=[str(script)],
                         env=dict(os.environ, CONNECTED_KNOWLEDGE_PRIVATE_CONFIG=str(cfg)))
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.assertEqual([t.name for t in tools], ['save_selected_capture'])
                    props = tools[0].inputSchema['properties']
                    self.assertNotIn('destination', props)
                    self.assertNotIn('account', props)
                    self.assertTrue(tools[0].annotations.idempotentHint)
                    schema = tools[0].inputSchema
                    message_schema = schema['$defs']['SelectedMessage']
                    self.assertEqual(set(message_schema['required']), {'id', 'role', 'text'})
                    self.assertFalse(message_schema['additionalProperties'])
                    args = {'source': 'chatgpt', 'conversation_id': 'fictional-chat',
                            'capture_id': 'fictional-selection', 'title': 'Synthetic orchard',
                            'coverage': 'summary', 'messages': [
                                {'id': 'summary', 'role': 'assistant', 'text': 'Fictional pears chosen.'}]}
                    first = await session.call_tool('save_selected_capture', args)
                    self.assertFalse(first.isError, first.content)
                    self.assertEqual(json.loads(first.content[0].text)['status'], 'saved')
                    retry = await session.call_tool('save_selected_capture', args)
                    self.assertEqual(json.loads(retry.content[0].text)['status'], 'unchanged')
                    cfg.write_text(json.dumps({'enabled': False}))
                    disabled = await session.call_tool('save_selected_capture', args)
                    self.assertEqual(json.loads(disabled.content[0].text)['status'], 'error')
            self.assertEqual(len(list((root/'archive').glob('*.md'))), 1)
        with tempfile.TemporaryDirectory() as tmp:
            asyncio.run(exercise(Path(tmp).resolve()))


if __name__ == '__main__':
    unittest.main()
