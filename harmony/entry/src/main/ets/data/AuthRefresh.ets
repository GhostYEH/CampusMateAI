export type RefreshOperation = () => Promise<boolean>;

export class RefreshCoordinator {
  private inFlight: Promise<boolean> | null = null;

  run(operation: RefreshOperation): Promise<boolean> {
    if (this.inFlight !== null) {
      return this.inFlight;
    }
    const flight: Promise<boolean> = operation();
    this.inFlight = flight;
    flight.then(() => { this.finish(flight); }).catch(() => { this.finish(flight); });
    return flight;
  }

  private finish(flight: Promise<boolean>): void {
    if (this.inFlight === flight) {
      this.inFlight = null;
    }
  }
}
