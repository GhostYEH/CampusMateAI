/** Return failed drafts separately so retrying a partial batch cannot recreate successful tasks. */
export async function saveBreakdownTasks(steps, goal, createTask) {
  const valid = steps.filter((step) => step.title.trim());
  const results = await Promise.allSettled(valid.map(async (step) => createTask({
    title: step.title.trim(),
    description: step.description?.trim() || undefined,
    source_name: "AI 拆解步骤",
    source_text: goal,
  })));
  const failedSteps = valid.filter((_, index) => results[index].status === "rejected");
  return { savedCount: valid.length - failedSteps.length, failedSteps };
}
