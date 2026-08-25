export interface EduConnectionRequestToken {
  generation: number;
  connectionId: string;
}

/** Keeps asynchronous connection responses scoped to the connection that started them. */
export class EduConnectionRequestGuard {
  private generation: number = 0;
  private expectedConnectionId: string | undefined = undefined;

  beginReplacement(): number {
    this.generation += 1;
    this.expectedConnectionId = undefined;
    return this.generation;
  }

  invalidate(): number {
    return this.beginReplacement();
  }

  isGenerationCurrent(generation: number): boolean {
    return generation === this.generation;
  }

  acceptCreatedConnection(generation: number, connectionId: string): boolean {
    if (!this.isGenerationCurrent(generation) || this.expectedConnectionId !== undefined) return false;
    this.expectedConnectionId = connectionId;
    return true;
  }

  capture(connectionId: string): EduConnectionRequestToken | undefined {
    if (this.expectedConnectionId !== connectionId) return undefined;
    return { generation: this.generation, connectionId: connectionId };
  }

  isCurrent(token: EduConnectionRequestToken, resultConnectionId: string): boolean {
    return token.generation === this.generation &&
      token.connectionId === this.expectedConnectionId &&
      resultConnectionId === token.connectionId;
  }

  commitIfCurrent(
    token: EduConnectionRequestToken,
    resultConnectionId: string,
    commit: () => void
  ): boolean {
    if (!this.isCurrent(token, resultConnectionId)) return false;
    commit();
    return true;
  }
}
