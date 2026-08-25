from expression_recognition.quality import FaceQualityMetrics, assess_face_quality


def test_small_face_is_rejected_before_other_checks() -> None:
    result = assess_face_quality(FaceQualityMetrics(
        face_ratio=0.08,
        sharpness=50.0,
        pitch=0.0,
        yaw=0.0,
        roll=0.0,
        brightness=120.0,
        face_count=1,
    ))

    assert result.accepted is False
    assert result.reason == "TOO_SMALL"


def test_multiple_faces_are_rejected_to_protect_bystanders() -> None:
    result = assess_face_quality(FaceQualityMetrics(
        face_ratio=0.30,
        sharpness=50.0,
        pitch=0.0,
        yaw=0.0,
        roll=0.0,
        brightness=120.0,
        face_count=2,
    ))

    assert result.accepted is False
    assert result.reason == "MULTIPLE_FACES"


def test_dark_blurry_or_extreme_pose_faces_are_rejected() -> None:
    base = dict(face_ratio=0.30, face_count=1)
    assert assess_face_quality(FaceQualityMetrics(**base, sharpness=10, pitch=0, yaw=0, roll=0, brightness=120)).reason == "BLUR"
    assert assess_face_quality(FaceQualityMetrics(**base, sharpness=50, pitch=0, yaw=31, roll=0, brightness=120)).reason == "EXTREME_POSE"
    assert assess_face_quality(FaceQualityMetrics(**base, sharpness=50, pitch=0, yaw=0, roll=0, brightness=25)).reason == "LOW_LIGHT"


def test_clear_single_face_is_accepted() -> None:
    result = assess_face_quality(FaceQualityMetrics(
        face_ratio=0.30,
        sharpness=50.0,
        pitch=5.0,
        yaw=-8.0,
        roll=4.0,
        brightness=120.0,
        face_count=1,
    ))

    assert result.accepted is True
    assert result.reason == "ACCEPTED"
