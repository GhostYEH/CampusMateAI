package com.example.campusai.ui.screens.lostfound

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.campusai.data.repository.LostFoundRepository
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.LoadingState
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background

@Composable
fun MyLostFoundScreen(
    repository: LostFoundRepository,
    onBack: () -> Unit,
    onOpenDetail: (Long) -> Unit,
) {
    val items by repository.items.collectAsState()
    val loading by repository.loading.collectAsState()
    val mine = items.filter { it.mine }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp),
    ) {
        Spacer(Modifier.height(14.dp))
        when {
            loading -> LoadingState()
            mine.isEmpty() -> EmptyState(Icons.Default.Inventory2, CampusStrings.LostFound.EMPTY)
            else -> LazyColumn(
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(
                    bottom = WindowInsets.navigationBars.asPaddingValues()
                        .calculateBottomPadding() + BottomDockReservedHeight + 16.dp,
                ),
            ) {
                items(mine, key = { it.id }) { item ->
                    LostFoundCard(item, onClick = { onOpenDetail(item.id) })
                }
            }
        }
    }
}
