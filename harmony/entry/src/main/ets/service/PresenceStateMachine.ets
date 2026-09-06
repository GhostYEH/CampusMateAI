export enum PresenceState {
  PRESENT = 'PRESENT',
  OBSERVING = 'OBSERVING',
  ABSENT = 'ABSENT'
}

export interface PresenceConfig {
  personHoldMs: number;
  presenceGraceMs: number;
}

export interface PresenceSnapshot {
  state: PresenceState;
  lastPresenceEvidenceAtMs: number | undefined;
  personDetected: boolean;
  recentPersonEvidence: boolean;
  faceDetected: boolean;
  behaviorEvidence: boolean;
}

/**
 * Conservatively fuses independently-produced, current evidence. Either a face
 * or an already-stable VISIBLE_STUDY result immediately restores PRESENT.
 */
export class PresenceStateMachine {
  private readonly config: PresenceConfig;
  private state: PresenceState = PresenceState.OBSERVING;
  private lastPresenceEvidenceAtMs: number | undefined = undefined;
  private lastPersonDetectedAtMs: number | undefined = undefined;

  constructor(config?: PresenceConfig) {
    this.config = config ?? { personHoldMs: 2000, presenceGraceMs: 12000 };
  }

  reset(): void {
    this.state = PresenceState.OBSERVING;
    this.lastPresenceEvidenceAtMs = undefined;
    this.lastPersonDetectedAtMs = undefined;
  }

  process(timestampMs: number, personDetected: boolean, faceDetected: boolean,
    behaviorEvidence: boolean): PresenceSnapshot {
    if (personDetected) {
      this.lastPersonDetectedAtMs = timestampMs;
    }
    const recentPersonEvidence: boolean = this.lastPersonDetectedAtMs !== undefined &&
      timestampMs - this.lastPersonDetectedAtMs <= this.config.personHoldMs;
    if (recentPersonEvidence || faceDetected || behaviorEvidence) {
      this.lastPresenceEvidenceAtMs = timestampMs;
      this.state = PresenceState.PRESENT;
    } else {
      const lastEvidenceAt: number | undefined = this.lastPresenceEvidenceAtMs;
      if (lastEvidenceAt === undefined) {
        this.state = PresenceState.OBSERVING;
      } else if (timestampMs - lastEvidenceAt >= this.config.presenceGraceMs) {
        this.state = PresenceState.ABSENT;
      } else {
        this.state = PresenceState.PRESENT;
      }
    }
    return {
      state: this.state,
      lastPresenceEvidenceAtMs: this.lastPresenceEvidenceAtMs,
      personDetected: personDetected,
      recentPersonEvidence: recentPersonEvidence,
      faceDetected: faceDetected,
      behaviorEvidence: behaviorEvidence
    };
  }
}