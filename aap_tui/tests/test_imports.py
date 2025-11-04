def test_imports():
    import aap_tui
    from aap_tui.app import AAPTui
    from aap_tui.services.controller import ControllerClient
    from aap_tui.models.jobs import Job, JobEvent
    assert AAPTui and ControllerClient and Job and JobEvent
