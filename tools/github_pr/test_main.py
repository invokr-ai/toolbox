import importlib.util
import tempfile
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("tool_under_test", HERE/"main.py")
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
HOST='api.github.com'
ARGS={'repo':'octo/demo','head':'feature/x','base':'main','title':'Add x','body':'why','draft':True}
CASES=[(ARGS, {'number':7,'html_url':'https://github.com/octo/demo/pull/7','state':'open','draft':True,'user':{'login':'octo'}},
        {'number':7,'url':'https://github.com/octo/demo/pull/7','state':'open','draft':True},
        ['/repos/octo/demo/pulls','POST',{'title':'Add x','head':'feature/x','base':'main','body':'why','draft':True}])]

class Tests(unittest.TestCase):
    def test_operations_offline(self):
        for args, response, expected, call in CASES:
            with self.subTest(args=args), patch.object(tool, 'api', return_value=response) as api:
                self.assertEqual(tool.run(args), expected)
                self.assertEqual(api.call_args.args, tuple(call))

    def test_url_policy(self):
        for url in ['http://'+HOST, 'https://127.0.0.1/', 'https://'+HOST+':444/',
                    'https://evil.invalid/', 'https://user:pass@'+HOST, 'https://'+HOST+'/#fragment',
                    'https://'+HOST+'/\r\nx']:
            with self.subTest(url=url), patch.object(tool.socket,"getaddrinfo") as dns:
                with self.assertRaises(ValueError): tool.request(url)
                dns.assert_not_called()

    def test_private_and_mixed_dns_denied(self):
        for addresses in [['127.0.0.1'],['169.254.169.254'],['10.0.0.1'],['::1'],['93.184.216.34','127.0.0.1']]:
            answers=[(2,1,6,'',(ip,443)) for ip in addresses]
            with patch.object(tool.socket,'getaddrinfo',return_value=answers), patch.object(tool.socket,'socket') as sock:
                with self.assertRaises(ValueError): tool.request('https://'+HOST+'/')
                sock.assert_not_called()

    def test_pins_ip_verifies_tls_and_closes(self):
        answers=[(2,1,6,'',('93.184.216.34',443))]
        with patch.object(tool.socket,'getaddrinfo',return_value=answers) as dns, patch.object(tool.socket,'socket') as sock, patch.object(tool.ssl,'create_default_context') as tls, patch.object(tool.http.client,'HTTPSConnection') as client:
            response=client.return_value.getresponse.return_value
            response.status=200
            response.getheader.side_effect=lambda key,default='': {'Content-Encoding':'identity','Content-Type':'text/plain'}.get(key,default)
            response.read.return_value=b'hello'
            self.assertEqual(tool.request('https://'+HOST+'/path?q=x'),(200,'text/plain',b'hello'))
            dns.assert_called_once()
            sock.return_value.connect.assert_called_once_with(('93.184.216.34',443))
            tls.return_value.wrap_socket.assert_called_once_with(sock.return_value,server_hostname=HOST)
            response.read.assert_called_once_with(65537)
            client.return_value.close.assert_called_once()
            sock.return_value.close.assert_called_once()

    def test_redirect_status_compression_and_oversize_denied(self):
        for status,encoding,body in [(302,'identity',b''),(500,'identity',b''),(200,'gzip',b''),(200,'identity',b'x'*65537)]:
            with patch.object(tool.socket,'getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]), patch.object(tool.socket,'socket'), patch.object(tool.ssl,'create_default_context'), patch.object(tool.http.client,'HTTPSConnection') as client:
                response=client.return_value.getresponse.return_value
                response.status=status
                response.getheader.side_effect=lambda key,default='': encoding if key=='Content-Encoding' else 'text/plain'
                response.read.return_value=body
                with self.assertRaises(ValueError): tool.request('https://'+HOST+'/')
                client.return_value.close.assert_called_once()

    def test_protocol_errors_offline(self):
        name=json.loads((HERE/'plugin.json').read_text())['name']
        for raw in ['{',json.dumps({'name':name,'arguments':{}}),json.dumps({'name':name,'arguments':{'unexpected':1}})]:
            result=subprocess.run([sys.executable,'-I','-B',str(HERE/'main.py')],input=raw,text=True,capture_output=True,timeout=3,env={'PATH':os.defpath})
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('error',json.loads(result.stdout))


    def test_auth_is_explicit_and_scoped(self):
        with patch.object(tool, 'token', return_value='FAKE-TEST-TOKEN'), patch.object(tool, 'request', return_value=(200, 'application/json', b'{"ok":true}')) as req:
            self.assertEqual(tool.api('/test', 'POST', {'x': 1}), {'ok': True})
            url, method, body, headers = req.call_args.args
            self.assertEqual(url, tool.ORIGIN + '/test')
            self.assertEqual(method, 'POST')
            self.assertEqual(json.loads(body), {'x': 1})
            self.assertEqual(headers['Authorization'], tool.AUTH_PREFIX + 'FAKE-TEST-TOKEN')

    def test_secret_permissions_symlinks_and_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / 'main.py'
            secret = Path(temp) / '.secrets.json'
            with patch.object(tool, '__file__', str(fake)):
                with self.assertRaises(ValueError): tool.token()
                secret.write_text('{"token":"FAKE-TEST-TOKEN"}')
                secret.chmod(0o600)
                self.assertEqual(tool.token(), 'FAKE-TEST-TOKEN')
                secret.chmod(0o644)
                with self.assertRaises(ValueError): tool.token()
                secret.chmod(0o600)
                for raw in ['{', '{"token":"bad\\nheader"}', '{"token":42}', 'x'*8193]:
                    secret.write_text(raw)
                    with self.assertRaises(ValueError): tool.token()
                secret.unlink()
                secret.symlink_to(fake)
                with self.assertRaises(ValueError): tool.token()

    def test_provider_errors_do_not_echo_response(self):
        for raw in [b'FAKE-SECRET-BODY', b'"FAKE-SECRET-BODY"']:
            with patch.object(tool, 'token', return_value='FAKE'), patch.object(tool, 'request', return_value=(200, 'application/json', raw)):
                with self.assertRaises(ValueError) as error: tool.api('/test')
                self.assertNotIn('FAKE-SECRET-BODY', str(error.exception))

    def test_path_injection_rejected(self):
        for value in ['../secret', 'octo', 'octo/demo/pulls', 'octo/demo?x=1', 'octo/..', '']:
            with self.subTest(repo=value), patch.object(tool,'api') as api:
                with self.assertRaises(ValueError): tool.run(dict(ARGS, repo=value))
                api.assert_not_called()
        for value in ['../main', '-x', 'a b', 'x.lock', 'x/', '']:
            with self.subTest(head=value), patch.object(tool,'api') as api:
                with self.assertRaises(ValueError): tool.run(dict(ARGS, head=value))
                api.assert_not_called()

    def test_empty_title_rejected(self):
        with patch.object(tool,'api') as api:
            with self.assertRaises(ValueError): tool.run(dict(ARGS, title='  '))
            api.assert_not_called()

if __name__ == '__main__': unittest.main()
