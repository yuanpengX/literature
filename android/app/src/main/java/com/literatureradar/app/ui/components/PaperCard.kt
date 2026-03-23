package com.literatureradar.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.Alignment
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.literatureradar.app.data.PaperJson
import com.literatureradar.app.data.feedBlurbRedundantWithAbstract
import com.literatureradar.app.data.stripHtmlToPlain

@Composable
fun PaperCard(
    paper: PaperJson,
    position: Int,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    /** 每日精选等场景：展示一句推荐理由 */
    pickBlurb: String? = null,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (paper.rankTags.isNotEmpty()) {
                    for (t in paper.rankTags) {
                        val label = when (t) {
                            "trending" -> "热"
                            "fresh" -> "新"
                            else -> t
                        }
                        val col = when (t) {
                            "trending" -> MaterialTheme.colorScheme.primary
                            "fresh" -> MaterialTheme.colorScheme.tertiary
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        }
                        Text(
                            text = label,
                            style = MaterialTheme.typography.labelSmall,
                            color = col,
                            modifier = Modifier.padding(end = 4.dp),
                        )
                    }
                } else {
                    paper.rankReason?.let { reason ->
                        val label = when (reason) {
                            "trending" -> "热"
                            "for_you" -> "兴趣"
                            else -> reason
                        }
                        Text(
                            text = label,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.padding(end = 4.dp),
                        )
                    }
                }
                Text(
                    text = paper.source,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (paper.citationCount > 0) {
                    Text(
                        text = "引用 ${paper.citationCount}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Text(
                text = paper.title,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
            )
            if (paper.authorsText.isNotBlank()) {
                Text(
                    text = paper.authorsText,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "阅读价值",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(2.dp), verticalAlignment = Alignment.CenterVertically) {
                    val n = paper.readValueStars.coerceIn(1, 5)
                    repeat(n) {
                        Text(
                            text = "★",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                    repeat(5 - n) {
                        Text(
                            text = "☆",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.outline.copy(alpha = 0.45f),
                        )
                    }
                }
            }
            val abstractPlain = paper.abstract.stripHtmlToPlain()
            val blurbRaw = pickBlurb?.takeIf { it.isNotBlank() } ?: paper.feedBlurb.takeIf { it.isNotBlank() }
            val blurbLine = blurbRaw?.takeIf { !feedBlurbRedundantWithAbstract(it, abstractPlain) }
            blurbLine?.let { blurb ->
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
                ) {
                    Text(
                        text = blurb,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                    )
                }
            }
        }
    }
}
