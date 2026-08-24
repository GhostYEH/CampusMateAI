import appStateTest from './ets/core/AppState.test';
import apiResponseTest from './ets/data/ApiResponse.test';
import authRefreshTest from './ets/data/AuthRefresh.test';
import focusModeMapperTest from './ets/data/FocusModeMapper.test';
import notificationSourceResolverTest from './ets/notification/NotificationSourceResolver.test';
import notificationFilterTest from './ets/notification/NotificationFilter.test';
import groupNameNormalizerTest from './ets/notification/GroupNameNormalizer.test';
import notificationFingerprintTest from './ets/notification/NotificationFingerprint.test';
import notificationBatchTest from './ets/notification/NotificationBatch.test';
import notificationCapabilityTest from './ets/notification/NotificationCapability.test';
import v3CoreContractTest from './ets/data/V3CoreContract.test';
import motionSpecTest from './ets/ui/MotionSpec.test';
import behaviorV34DecisionTest from './ets/data/BehaviorV34Decision.test';

export default function testsuite(): void {
  appStateTest();
  apiResponseTest();
  authRefreshTest();
  focusModeMapperTest();
  notificationSourceResolverTest();
  notificationFilterTest();
  groupNameNormalizerTest();
  notificationFingerprintTest();
  notificationBatchTest();
  notificationCapabilityTest();
  v3CoreContractTest();
  motionSpecTest();
  behaviorV34DecisionTest();
}
