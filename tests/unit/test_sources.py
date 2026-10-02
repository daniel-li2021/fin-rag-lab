import socket
import pytest
from src.loaders.text_loader import load_text
from src.storage.fetch import normalize_url,public_addresses,fetch_snapshot
from src.chunkers import ParentChildChunker


def test_parser_configuration_cache_isolation(tmp_path):
    from tests.integration.make_test_pdf import make_test_pdf
    from src.pipelines.ingestion import IngestionPipeline
    from src.captioners.vlm_captioner import NoOpCaptioner
    path=tmp_path/'source.pdf';make_test_pdf(path)
    pipeline=IngestionPipeline(cache_root=tmp_path/'cache',captioner=NoOpCaptioner())
    assert not pipeline.ingest(path).parse_cache_hit
    assert pipeline.ingest(path).parse_cache_hit
    pipeline.parser.heading_max_chars+=1
    assert not pipeline.ingest(path).parse_cache_hit


def test_text_markdown_provenance_and_validation():
    doc=load_text(b'# Report\n\nRevenue 42\nCash 8\n','markdown','Report')
    _,children=ParentChildChunker().chunk_with_parents(doc)
    span=next(s for c in children for s in c.evidence_spans if 'Revenue' in s.text)
    assert span.line_start==3 and span.line_end==4 and span.heading_path==['Report']
    for data in (b'',b'\xff',b'a\x00b'):
        with pytest.raises((ValueError,UnicodeError)):
            load_text(data,'text','Bad')
    assert 'evil' not in load_text(b'<p>Revenue 42</p><script>evil()</script>','html','HTML').text


def test_url_validation_and_dns(monkeypatch):
    assert normalize_url('https://EXAMPLE.com/report#part')=='https://example.com/report'
    for url in ('file:///a','https://user:pw@example.com','http://example.com:8080','http://example.com\r\nX:1'):
        with pytest.raises(ValueError):normalize_url(url)
    for address in ('127.0.0.1','10.0.0.1','169.254.169.254','::1','::ffff:127.0.0.1'):
        monkeypatch.setattr(socket,'getaddrinfo',lambda *a,ip=address,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,80))])
        with pytest.raises(ValueError):public_addresses('host',80)


def test_snapshot_redirect_limits_and_change(monkeypatch):
    import src.storage.fetch as f
    events=[]
    class Response:
        status=200
        def __init__(self,body=b'Revenue 42',headers=None,status=200):
            self.body=body;self.headers=headers or {'Content-Type':'text/plain'};self.status=status
        def getheader(self,k,default=None):return self.headers.get(k,default)
        def read1(self,n):part,self.body=self.body[:n],self.body[n:];return part
    responses=[]
    class Connection:
        sock=None
        def __init__(self,host,*a,**k):events.append(host)
        def request(self,*a,**k):pass
        def getresponse(self):return responses.pop(0)
        def close(self):pass
    monkeypatch.setattr(f,'HTTPConnection',Connection)
    monkeypatch.setattr(f,'HTTPSConnection',Connection)
    def public(host,*a):
        if host=='private':raise ValueError('private')
        return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
    monkeypatch.setattr(f,'public_addresses',public)
    responses.append(Response(status=302,headers={'Location':'http://private/'}))
    with pytest.raises(ValueError):fetch_snapshot('https://public/')
    assert events==['public']
    responses.append(Response(body=b'x'*6))
    with pytest.raises(ValueError):fetch_snapshot('https://public/',max_bytes=5)
    responses.extend([Response(body=b'Revenue 42'),Response(body=b'Revenue 50')])
    assert fetch_snapshot('https://public/')[0]!=fetch_snapshot('https://public/')[0]
