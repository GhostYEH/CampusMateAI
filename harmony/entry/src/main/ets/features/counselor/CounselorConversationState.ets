export class CounselorConversationState {
  static showSuggestions(messageCount: number): boolean {
    return messageCount === 0;
  }
}
