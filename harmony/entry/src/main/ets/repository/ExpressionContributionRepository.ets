import { ApiClient } from '../data/ApiClient';
import { ExpressionContributionResponse } from '../data/Models';

export class ExpressionContributionRepository {
  private readonly client: ApiClient;

  constructor(client: ApiClient) {
    this.client = client;
  }

  async upload(fileUri: string, fileName: string, contentType: string,
    label: string): Promise<ExpressionContributionResponse> {
    return this.client.uploadExpressionContribution(
      fileUri, fileName, contentType, label, 'true', 'client-expression-v1'
    );
  }

  async delete(sampleId: string): Promise<ExpressionContributionResponse> {
    return this.client.deleteExpressionContribution(sampleId);
  }
}