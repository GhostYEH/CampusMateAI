"""共享服务必须在构造时就收到完整依赖，避免启动期间出现半初始化实例。"""
from app.core.config import Settings
from app.database.sqlite_db import Database
from app.services import container as container_module


def test_learning_services_receive_shared_dependencies_at_construction(monkeypatch, tmp_path):
    snapshots = {}
    service_names = (
        "ModelShadowRunner", "LearnerEventService", "LearnerStateProjectionService",
        "LearningPlannerService", "AdaptiveInterventionService", "ForecastService", "EduConnectorService",
    )
    for name in service_names:
        service_class = getattr(container_module, name)

        def construct(*args, _name=name, _class=service_class, **kwargs):
            snapshots[_name] = dict(kwargs)
            return _class(*args, **kwargs)

        monkeypatch.setattr(container_module, name, construct)
    database = Database(None)
    try:
        services = container_module._build_container_inner(Settings(
            app_env="test", llm_provider="none", auto_seed_demo_users=False,
            auto_import_demo=False, agent_artifact_path=str(tmp_path / "artifacts"),
        ), database)
        for name in ("ModelShadowRunner", "LearnerEventService", "LearnerStateProjectionService", "LearningPlannerService"):
            assert snapshots[name]["source_policy"] is services.learner_model_source_policy
        for name in ("LearnerEventService", "LearnerStateProjectionService", "ForecastService"):
            assert snapshots[name]["edu_data_repository"] is snapshots["EduConnectorService"]["edu_data_repo"]
        assert snapshots["LearnerEventService"]["edu_repository"] is services.edu_repository
        assert snapshots["LearnerEventService"]["notice_repository"] is services.notice_repository
        assert snapshots["LearnerStateProjectionService"]["learner_event_repository"] is services.learner_event_repository
        assert snapshots["LearnerStateProjectionService"]["student_goal_repository"] is services.student_goal_repository
        assert snapshots["LearningPlannerService"]["notice_repository"] is services.notice_repository
        for name in ("LearningPlannerService", "AdaptiveInterventionService"):
            assert snapshots[name]["forecast_service"] is services.forecast_service
    finally:
        database.dispose()
