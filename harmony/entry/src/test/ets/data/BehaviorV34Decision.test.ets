import { describe, expect, it } from '@ohos/hypium';
import {
  BehaviorReminderTracker,
  BehaviorV34Decision,
  BehaviorV34Label,
  BehaviorV34Result
} from '../../../main/ets/service/BehaviorV34Decision';

function stable(label: BehaviorV34Label): BehaviorV34Result {
  return { label: label, confidence: 0.8, margin: 0.6, isStable: true, probabilities: [0.8, 0.1, 0.05, 0.05] };
}

export default function behaviorV34DecisionTest(): void {
  describe('BehaviorV34Decision', () => {
    it('maps the four logits in model-card order', 0, () => {
      expect(BehaviorV34Decision.decode([10, 0, 0, 0]).label).assertEqual(BehaviorV34Label.READ);
      expect(BehaviorV34Decision.decode([0, 10, 0, 0]).label).assertEqual(BehaviorV34Label.WRITE);
      expect(BehaviorV34Decision.decode([0, 0, 10, 0]).label).assertEqual(BehaviorV34Label.PHONE_INTERACTION);
      expect(BehaviorV34Decision.decode([0, 0, 0, 10]).label).assertEqual(BehaviorV34Label.NO_VISIBLE_STUDY);
    });

    it('exports the computer label for hybrid display decisions', 0, () => {
      expect(BehaviorV34Label.COMPUTER).assertEqual('COMPUTER');
    });

    it('rejects an unreliable decision as continue observing', 0, () => {
      const result: BehaviorV34Result = BehaviorV34Decision.decode([1, 1, 0, 0]);
      expect(result.isStable).assertFalse();
      expect(result.label).assertEqual(BehaviorV34Label.CONTINUE_OBSERVING);
    });

    it('reminds only after sustained phone interaction', 0, () => {
      const tracker: BehaviorReminderTracker = new BehaviorReminderTracker();
      expect(tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 1000)).assertEqual('');
      expect(tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 3999)).assertEqual('');
      expect(tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 4000).length > 0).assertTrue();
    });

    it('does not start or clear timing for rejected frames', 0, () => {
      const tracker: BehaviorReminderTracker = new BehaviorReminderTracker();
      const rejected: BehaviorV34Result = BehaviorV34Decision.decode([1, 1, 0, 0]);
      tracker.process(stable(BehaviorV34Label.NO_VISIBLE_STUDY), 1000);
      tracker.process(rejected, 15000);
      expect(tracker.process(stable(BehaviorV34Label.NO_VISIBLE_STUDY), 21000).length > 0).assertTrue();
    });

    it('clears the behavior reminder after reading or writing resumes', 0, () => {
      const tracker: BehaviorReminderTracker = new BehaviorReminderTracker();
      tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 1000);
      tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 4000);
      expect(tracker.process(stable(BehaviorV34Label.READ), 5000)).assertEqual('');
    });

    it('uses phone exit hysteresis and reminder cooldown', 0, () => {
      const tracker: BehaviorReminderTracker = new BehaviorReminderTracker();
      tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 1000);
      expect(tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 4000).length > 0).assertTrue();
      expect(tracker.process(stable(BehaviorV34Label.READ), 4500).length > 0).assertTrue();
      expect(tracker.process(stable(BehaviorV34Label.READ), 5000)).assertEqual('');
      tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 6000);
      expect(tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 9000)).assertEqual('');
    });
  });
}
