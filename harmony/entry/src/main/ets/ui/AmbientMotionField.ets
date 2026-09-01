import { CampusPalette, darkPalette, lightPalette } from './Theme';
import { MotionDuration, MotionSpec } from './MotionSpec';

interface AmbientOrbSpec {
  x: number;
  y: number;
  size: number;
  color: string;
  phase: number;
}

const AMBIENT_ORBS: AmbientOrbSpec[] = [
  { x: 7, y: 13, size: 8, color: '#FF5B68F2', phase: 0 },
  { x: 20, y: 7, size: 5, color: '#FF7DC8FF', phase: 1 },
  { x: 86, y: 11, size: 10, color: '#FF8D84FF', phase: 0 },
  { x: 95, y: 28, size: 5, color: '#FF5B68F2', phase: 1 },
  { x: 5, y: 53, size: 7, color: '#FFFFB078', phase: 0 },
  { x: 92, y: 65, size: 8, color: '#FF7DC8FF', phase: 1 },
  { x: 15, y: 84, size: 5, color: '#FF8D84FF', phase: 1 },
  { x: 84, y: 89, size: 7, color: '#FF5B68F2', phase: 0 }
];

@Component
export struct AmbientMotionField {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @State phase: number = 0;
  private timerId: number = -1;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  aboutToAppear(): void {
    if (!this.reduceMotion) {
      this.timerId = setInterval(() => {
        this.phase = this.phase === 0 ? 1 : 0;
      }, MotionDuration.AMBIENT);
    }
  }

  aboutToDisappear(): void {
    if (this.timerId >= 0) {
      clearInterval(this.timerId);
      this.timerId = -1;
    }
  }

  @Builder
  Orb(spec: AmbientOrbSpec) {
    Circle()
      .width(spec.size)
      .height(spec.size)
      .fill(spec.color)
      .position({ x: `${spec.x}%`, y: `${spec.y}%` })
      .opacity(MotionSpec.ambientOpacity(this.reduceMotion))
      .scale({
        x: this.phase === spec.phase ? 1.42 : 0.92,
        y: this.phase === spec.phase ? 1.42 : 0.92
      })
      .translate({
        x: MotionSpec.parallaxAmplitude(this.reduceMotion, this.phase === spec.phase ? 5 : -5),
        y: MotionSpec.parallaxAmplitude(this.reduceMotion, this.phase === spec.phase ? -4 : 4)
      })
      .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.AMBIENT), curve: Curve.Smooth })
      .hitTestBehavior(HitTestMode.None);
  }

  build() {
    Stack() {
      ForEach(AMBIENT_ORBS, (orb: AmbientOrbSpec) => {
        this.Orb(orb);
      });
    }
    .width('100%')
    .height('100%')
    .opacity(MotionSpec.ambientOpacity(this.reduceMotion) > 0 ? 1 : 0)
    .hitTestBehavior(HitTestMode.None);
  }
}
