"""The asset pipeline: a page must never reference an asset the app cannot serve."""
import re

from src.survey import app as app_module

ASSET_RE = re.compile(r'(?:src|href)="(/[^"]+)"')


def make_build(tmp_path, files=('style.css',), manifest_entry=None):
    app_module.STATIC_DIST = str(tmp_path)
    app_module.BUILT_ASSETS = set(files)
    app_module.BUNDLE_ENTRIES = manifest_entry or {}


def asset_urls(html):
    return [url for url in ASSET_RE.findall(html) if not url.startswith('data:')]


def test_every_page_serves_the_assets_it_references(client):
    for path in ('/', '/admin/login'):
        page = client.get(path)
        assert page.status_code == 200, (path, page.status_code, page.get_data(as_text=True)[:200])
        for url in asset_urls(page.get_data(as_text=True)):
            served = client.get(url)
            assert served.status_code == 200, f'{path} references a dead asset {url}'


def test_a_build_takes_over_from_the_source_static_files(client, app, tmp_path, monkeypatch):
    (tmp_path / 'style.css').write_text('body{color:red}')
    monkeypatch.setattr(app_module, 'STATIC_DIST', str(tmp_path))
    monkeypatch.setattr(app_module, 'BUILT_ASSETS', {'style.css'})

    body = client.get('/admin/login').get_data(as_text=True)
    assert 'href="/dist/style.css"' in body
    assert client.get('/dist/style.css').get_data(as_text=True) == 'body{color:red}'


def test_the_built_bundle_is_linked_when_the_manifest_has_it(client, app, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'STATIC_DIST', str(tmp_path))
    monkeypatch.setattr(app_module, 'BUILT_ASSETS', set())
    monkeypatch.setattr(app_module, 'BUNDLE_ENTRIES', {'survey': 'assets/survey-abc123.js'})

    body = client.get('/').get_data(as_text=True)
    assert '<script type="module" src="/dist/assets/survey-abc123.js"></script>' in body
    assert 'assets-missing' not in body


def test_an_unbuilt_checkout_renders_no_bundle_tag(client, app, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'STATIC_DIST', str(tmp_path))
    monkeypatch.setattr(app_module, 'BUILT_ASSETS', set())
    monkeypatch.setattr(app_module, 'BUNDLE_ENTRIES', {})

    body = client.get('/').get_data(as_text=True)
    assert 'type="module"' not in body
    assert 'assets-missing' in body, 'a survey page without a build must say so, not die silently'


def test_the_dist_route_refuses_to_climb_out_of_the_build_dir(client, app, tmp_path, monkeypatch):
    (tmp_path / 'style.css').write_text('x')
    make_build(tmp_path, files=('style.css',))
    monkeypatch.setattr(app_module, 'STATIC_DIST', str(tmp_path))

    for probe in ('/dist/style.css/../../app.py', '/dist/%2e%2e/app.py', '/dist/..%2fapp.py'):
        assert client.get(probe).status_code in (400, 404), probe


def login_admin(client):
    response = client.post('/admin/login', data={'password': 'admin123'})
    assert response.status_code in (200, 302)
    return client


def test_the_admin_page_links_its_bundle_and_warns_when_there_is_none(client, app, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'STATIC_DIST', str(tmp_path))
    monkeypatch.setattr(app_module, 'BUILT_ASSETS', set())
    monkeypatch.setattr(app_module, 'BUNDLE_ENTRIES', {})
    login_admin(client)

    unbuilt = client.get('/admin').get_data(as_text=True)
    assert 'assets-missing' in unbuilt, 'an unbuilt dashboard must say so, not render a dead table'

    monkeypatch.setattr(app_module, 'BUNDLE_ENTRIES', {'admin': 'assets/admin-abc123.js'})
    built = client.get('/admin').get_data(as_text=True)
    assert '<script type="module" src="/dist/assets/admin-abc123.js"></script>' in built
    assert 'assets-missing' not in built
