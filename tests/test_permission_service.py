from gui.services.permissions import PermissionService, PermissionContext


def test_permission_service_default_allow():
    svc = PermissionService()
    assert svc.can_open_team()
    assert svc.can_copy_team_id()
    assert svc.can_export_team()
    # Direct context usage
    assert svc.is_allowed(PermissionContext(actor_role="viewer", action="open"))


def test_permission_service_custom_policy():
    svc = PermissionService()
    # Inject a restrictive matrix
    svc._role_matrix["viewer"] = {"export": False, "copy_id": True, "open": True}
    assert svc.can_open_team("viewer") is True
    assert svc.can_copy_team_id("viewer") is True
    assert svc.can_export_team("viewer") is False
