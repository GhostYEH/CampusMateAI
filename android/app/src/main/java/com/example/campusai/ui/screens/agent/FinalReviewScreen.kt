package com.example.campusai.ui.screens.agent

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.data.remote.agent.AgentRiskLevel
import com.example.campusai.data.remote.agent.FinalReviewCampaignCreateRequest

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinalReviewScreen(
    viewModel: FinalReviewViewModel = viewModel(),
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadCampaigns() }

    Scaffold(topBar = { AgentTopBar("期末复习", onBack) }) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text("复习活动", style = MaterialTheme.typography.titleMedium)
            }
            if (state.loading && state.campaigns.isEmpty()) {
                item { Text("加载中…") }
            }
            items(state.campaigns) { campaign ->
                Card(onClick = { viewModel.openCampaign(campaign.campaignId) }) {
                    Column(Modifier.padding(16.dp)) {
                        Text("活动 ${campaign.campaignId.takeLast(8)}", style = MaterialTheme.typography.titleSmall)
                        Text("每日容量 ${campaign.dailyCapacityMinutes} 分钟", style = MaterialTheme.typography.bodySmall)
                        Text("状态 ${campaign.status}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            state.activeCampaign?.let { campaign ->
                item {
                    Text("当前活动", style = MaterialTheme.typography.titleMedium)
                }
                item {
                    Card {
                        Column(Modifier.padding(16.dp)) {
                            Text("版本 ${campaign.currentPlanVersion ?: "未生成"}")
                            if (state.generating) Text("生成中…") else {
                                Button(onClick = { viewModel.generatePlan(campaign.campaignId) }) { Text("生成计划") }
                                Spacer(Modifier.height(8.dp))
                                Button(onClick = { viewModel.activatePlan(campaign.campaignId) }) { Text("激活计划") }
                            }
                        }
                    }
                }
                item { Text("计划版本", style = MaterialTheme.typography.titleSmall) }
                items(state.planVersions) { version ->
                    ListItem(
                        headlineContent = { Text("v${version.version}") },
                        supportingContent = { Text("${version.summary} • ${version.status}") },
                    )
                }
                state.todayAgenda?.let { agenda ->
                    item { Text("今日议程", style = MaterialTheme.typography.titleSmall) }
                    items(agenda.items) { item ->
                        Card {
                            Row(Modifier.fillMaxWidth().padding(12.dp), Arrangement.SpaceBetween) {
                                Column(Modifier.weight(1f)) {
                                    Text(item.title, style = MaterialTheme.typography.bodyMedium)
                                    item.courseName?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                                }
                                Text("${item.estimatedMinutes}分钟")
                                Button(
                                    onClick = {
                                        viewModel.completeItem(
                                            item.itemId,
                                            com.example.campusai.data.remote.agent.FinalReviewEvidenceRequest(
                                                itemId = item.itemId,
                                                completed = true,
                                            ),
                                        )
                                    },
                                    enabled = item.status != "completed",
                                ) { Text("完成") }
                            }
                        }
                    }
                }
                if (state.adjustmentProposals.isNotEmpty()) {
                    item { Text("调整提案", style = MaterialTheme.typography.titleSmall) }
                    items(state.adjustmentProposals) { proposal ->
                        Card {
                            Column(Modifier.padding(16.dp)) {
                                Text(proposal.summary, style = MaterialTheme.typography.bodyMedium)
                                Text("风险 ${proposal.risk()}", style = MaterialTheme.typography.bodySmall)
                                Text("状态 ${proposal.status}", style = MaterialTheme.typography.bodySmall)
                                if (proposal.status == "PENDING") {
                                    Row(Modifier.padding(top = 8.dp), Arrangement.spacedBy(8.dp)) {
                                        Button(onClick = { viewModel.decideProposal(proposal.proposalId, "APPROVED") }) { Text("批准") }
                                        OutlinedButton(onClick = { viewModel.decideProposal(proposal.proposalId, "REJECTED") }) { Text("拒绝") }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            state.error?.let { err ->
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                        Text(err, Modifier.padding(16.dp))
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun AgentTopBar(title: String, onBack: () -> Unit) {
    TopAppBar(
        title = { Text(title) },
        navigationIcon = { TextButton(onClick = onBack) { Text("返回") } },
    )
}