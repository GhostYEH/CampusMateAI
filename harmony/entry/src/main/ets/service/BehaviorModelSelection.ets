export enum BehaviorRuntimeModel {
  V34 = 'V34',
  V32 = 'V32',
  UNAVAILABLE = 'UNAVAILABLE'
}

export class BehaviorModelSelection {
  static select(v34Available: boolean, v32Available: boolean, hasPersonRoi: boolean,
    enableV34: boolean = true): BehaviorRuntimeModel {
    if (enableV34 && v34Available && hasPersonRoi) return BehaviorRuntimeModel.V34;
    if (v32Available) return BehaviorRuntimeModel.V32;
    return BehaviorRuntimeModel.UNAVAILABLE;
  }
}