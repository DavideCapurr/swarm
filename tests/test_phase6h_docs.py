from pathlib import Path

REQUIRED = [
    'docs/architecture/overview.md','docs/api/openapi.yaml','docs/api/ws-contract.md',
    'docs/operator/manual.md','docs/operator/training.md','docs/ops/runbook.md',
    'docs/security/disclosure.md','docs/compliance/gdpr.md','docs/compliance/drone-regulations.md',
    'docs/dev/onboarding.md','docs/dev/release-process.md',
]
FORBIDDEN = ['Intruder', 'Manual', 'fly drone', 'alarm', 'red-alert', 'red state']
WS_KINDS = ['session','unit','dock','sector','awareness','mission','anomaly_view','event','operator','stream']
OPENAPI_KEYS = ['/auth/login','/session','/actions/verify','/admin/reload-site-config','/ready','/metrics','/']


def test_required_docs_exist() -> None:
    for rel in REQUIRED:
        assert Path(rel).is_file(), rel


def test_readme_links_phase6h_docs() -> None:
    readme = Path('README.md').read_text()
    for rel in REQUIRED:
        assert rel in readme or rel.startswith('docs/compliance/') or rel.startswith('docs/dev/'), rel


def test_openapi_contains_key_routes() -> None:
    text = Path('docs/api/openapi.yaml').read_text()
    for route in OPENAPI_KEYS:
        assert route in text


def test_ws_contract_contains_all_kinds() -> None:
    text = Path('docs/api/ws-contract.md').read_text()
    for kind in WS_KINDS:
        assert f'`{kind}`' in text
    assert '?token=' in text


def test_forbidden_words_absent_in_new_docs() -> None:
    for rel in REQUIRED:
        text = Path(rel).read_text()
        for word in FORBIDDEN:
            assert word not in text, f'{word} found in {rel}'
