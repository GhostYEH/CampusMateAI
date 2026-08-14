import { describe, expect, it } from '@ohos/hypium';
import { RefreshCoordinator } from '../../../main/ets/data/AuthRefresh';

export default function authRefreshTest(): void {
  describe('RefreshCoordinator', () => {
    it('shares one in-flight refresh across concurrent callers', 0, async () => {
      let calls: number = 0;
      const coordinator: RefreshCoordinator = new RefreshCoordinator();
      const refresh = async (): Promise<boolean> => {
        calls += 1;
        await Promise.resolve();
        return true;
      };
      const results: boolean[] = await Promise.all([
        coordinator.run(refresh), coordinator.run(refresh), coordinator.run(refresh)
      ]);
      expect(calls).assertEqual(1);
      expect(results.filter((value: boolean) => value).length).assertEqual(3);
    });

    it('allows a later refresh after the previous flight completes', 0, async () => {
      let calls: number = 0;
      const coordinator: RefreshCoordinator = new RefreshCoordinator();
      const refresh = async (): Promise<boolean> => { calls += 1; return true; };
      await coordinator.run(refresh);
      await coordinator.run(refresh);
      expect(calls).assertEqual(2);
    });
  });
}
