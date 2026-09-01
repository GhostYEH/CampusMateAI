import { describe, expect, it } from '@ohos/hypium';
import {
  BehaviorSessionSummary,
  BehaviorReminderTracker,
  BehaviorSessionSummaryTracker,
  BehaviorV34Decision,
  BehaviorV34Label,
  BehaviorV34Result
} from '../../../main/ets/service/BehaviorV34Decision';
import { toStudyBehaviorSummary } from '../../../main/ets/service/FocusAssistProvider';

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

    it('builds a privacy-safe session aggregate without frame data', 0, () => {
      const tracker: BehaviorSessionSummaryTracker = new BehaviorSessionSummaryTracker();
      tracker.reset(1000);
      tracker.process(stable(BehaviorV34Label.READ), 1000, '');
      tracker.process(stable(BehaviorV34Label.READ), 2000, '');
      tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 3000, '');
      tracker.process(stable(BehaviorV34Label.PHONE_INTERACTION), 6000, '手机提醒');
      tracker.process(stable(BehaviorV34Label.NO_VISIBLE_STUDY), 7000, '');
      const summary = tracker.summary(9000, 'V3.4+TSM-V4');

      expect(summary.observed_seconds).assertEqual(8);
      expect(summary.study_seconds).assertEqual(2);
      expect(summary.phone_interaction_count).assertEqual(1);
      expect(summary.possible_distraction_count).assertEqual(1);
      expect(summary.reminder_count).assertEqual(1);
      expect(summary.model_version).assertEqual('V3.4+TSM-V4');
    });

    it('includes confirmed absences in the session aggregate and clears them on reset', 0, () => {
      const tracker: BehaviorSessionSummaryTracker = new BehaviorSessionSummaryTracker();
      tracker.reset(1000);
      tracker.recordAbsence();
      tracker.recordAbsence();
      expect(tracker.summary(2000, 'V3.4').absent_count).assertEqual(2);

      tracker.reset(3000);
      expect(tracker.summary(4000, 'V3.4').absent_count).assertEqual(0);
    });

    it('suspends observation without losing confirmed aggregate counts', 0, () => {
      const tracker: BehaviorSessionSummaryTracker = new BehaviorSessionSummaryTracker();
      tracker.reset(1000);
      tracker.process(stable(BehaviorV34Label.READ), 1000, '');
      tracker.process(stable(BehaviorV34Label.READ), 2000, '');
      tracker.recordAbsence();
      tracker.suspend(2500);
      tracker.resume(10000);
      tracker.process(stable(BehaviorV34Label.READ), 10000, '');
      tracker.process(stable(BehaviorV34Label.READ), 11000, '');
      const summary = tracker.summary(11000, 'V3.4');

      expect(summary.study_seconds).assertEqual(2);
      expect(summary.meaningful_switch_count).assertEqual(0);
      expect(summary.absent_count).assertEqual(1);
    });

    it('maps every local aggregate field into the study finish contract', 0, () => {
      const local: BehaviorSessionSummary = {
        observed_seconds: 90,
        study_seconds: 61,
        paused_seconds: 12,
        longest_continuous_study_seconds: 40,
        meaningful_switch_count: 3,
        phone_interaction_count: 1,
        possible_distraction_count: 2,
        absent_count: 4,
        reminder_count: 2,
        model_version: 'V3.4+TSM-V4'
      };

      const request = toStudyBehaviorSummary(local);

      expect(request?.observed_seconds).assertEqual(90);
      expect(request?.study_seconds).assertEqual(61);
      expect(request?.paused_seconds).assertEqual(12);
      expect(request?.longest_continuous_study_seconds).assertEqual(40);
      expect(request?.meaningful_switch_count).assertEqual(3);
      expect(request?.phone_interaction_count).assertEqual(1);
      expect(request?.possible_distraction_count).assertEqual(2);
      expect(request?.absent_count).assertEqual(4);
      expect(request?.reminder_count).assertEqual(2);
      expect(request?.model_version).assertEqual('V3.4+TSM-V4');
    });
  });
}
