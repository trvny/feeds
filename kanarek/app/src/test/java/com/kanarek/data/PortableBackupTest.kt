package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.charset.StandardCharsets.UTF_8

class PortableBackupTest {
    @Test
    fun roundTripPreservesPortableData() {
        val station =
            M3uCodec.parse(
                """
                #EXTM3U
                #EXTINF:-1 tvg-logo="https://example.com/logo.png" group-title="Radio" kanarek-kind="radio",Example FM
                https://example.com/live.mp3
                """.trimIndent(),
            ).single()
        val item =
            NewsItem(
                title = "Saved story",
                link = "https://example.com/story",
                summary = "Summary",
                imageUrl = "https://example.com/story.jpg",
                source = "Example",
                publishedAtMillis = 123L,
            )
        val record =
            SavedArticleCodec.encodeRecord(
                SavedArticleRecord(
                    item = item,
                    savedAtMillis = 456L,
                    offline =
                        OfflineArticleContent(
                            title = "Offline title",
                            author = "Author",
                            imageUrl = null,
                            content = "Plain offline text",
                            wordCount = 3,
                            storedAtMillis = 789L,
                        ),
                ),
            )
        val backup =
            PortableBackup(
                settings =
                    PortableSettings(
                        feeds = listOf("https://example.com/feed.xml"),
                        backendUrl = "https://worker.example.com",
                        intervalSeconds = 15,
                        headlinesMode = true,
                        offlineSavedArticles = true,
                        perSourceCap = 3,
                        topSources = setOf("Example"),
                        stations = listOf(station),
                        favoriteStationIds = setOf(station.id),
                        lastStationId = station.id,
                    ),
                notifications =
                    NewsNotificationConfig(
                        enabled = true,
                        selectedFeeds = listOf("https://example.com/feed.xml"),
                        configuredFeeds = listOf("https://example.com/feed.xml"),
                        quietHoursEnabled = true,
                        quietStartMinute = 23 * 60,
                        quietEndMinute = 6 * 60,
                    ),
                savedArticleRecords = setOf(record),
            )

        val decoded = PortableBackupCodec.decode(PortableBackupCodec.encode(backup))

        assertEquals(backup.settings.feeds, decoded.settings.feeds)
        assertEquals(backup.settings.backendUrl, decoded.settings.backendUrl)
        assertEquals(backup.settings.intervalSeconds, decoded.settings.intervalSeconds)
        assertEquals(backup.settings.headlinesMode, decoded.settings.headlinesMode)
        assertEquals(backup.settings.offlineSavedArticles, decoded.settings.offlineSavedArticles)
        assertEquals(backup.settings.perSourceCap, decoded.settings.perSourceCap)
        assertEquals(backup.settings.topSources, decoded.settings.topSources)
        assertEquals(listOf(station.streamUrl), decoded.settings.stations.map(Station::streamUrl))
        assertEquals(setOf(station.id), decoded.settings.favoriteStationIds)
        assertEquals(station.id, decoded.settings.lastStationId)
        assertEquals(backup.notifications, decoded.notifications)
        assertEquals(setOf(record), decoded.savedArticleRecords)
    }

    @Test
    fun rejectsUnsupportedVersion() {
        val xml =
            String(PortableBackupCodec.encode(emptyBackup()), UTF_8)
                .replace("version=\"1\"", "version=\"99\"")

        assertThrows(BackupFormatException::class.java) {
            PortableBackupCodec.decode(xml.toByteArray(UTF_8))
        }
    }

    @Test
    fun rejectsOversizedFileBeforeParsing() {
        val bytes = ByteArray(PortableBackupCodec.MAX_FILE_BYTES + 1)

        assertThrows(BackupTooLargeException::class.java) {
            PortableBackupCodec.decode(bytes)
        }
    }

    @Test
    fun rejectsInvalidSavedArticleRecord() {
        val invalid = emptyBackup().copy(savedArticleRecords = setOf("not-a-record"))

        assertThrows(BackupFormatException::class.java) {
            PortableBackupCodec.encode(invalid)
        }
    }

    @Test
    fun rejectsDoctypeAndExternalEntityInput() {
        val xml =
            """
            <?xml version="1.0"?>
            <!DOCTYPE backup [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
            <kanarek-backup version="1">&xxe;</kanarek-backup>
            """.trimIndent()

        assertThrows(BackupFormatException::class.java) {
            PortableBackupCodec.decode(xml.toByteArray(UTF_8))
        }
    }

    @Test
    fun disabledNotificationsDoNotGainSourcesDuringNormalization() {
        val normalized =
            PortableBackupValidator.validate(
                emptyBackup().copy(
                    notifications = NewsNotificationConfig(enabled = false),
                ),
            )

        assertFalse(normalized.notifications.enabled)
        assertTrue(normalized.notifications.selectedFeeds.isEmpty())
        assertEquals(normalized.settings.feeds, normalized.notifications.configuredFeeds)
    }

    private fun emptyBackup(): PortableBackup =
        PortableBackup(
            settings =
                PortableSettings(
                    feeds = listOf("https://example.com/feed.xml"),
                    backendUrl = "",
                    intervalSeconds = SettingsStore.DEFAULT_INTERVAL,
                    headlinesMode = false,
                    offlineSavedArticles = false,
                    perSourceCap = SettingsStore.DEFAULT_PER_SOURCE_CAP,
                    topSources = emptySet(),
                    stations = emptyList(),
                    favoriteStationIds = emptySet(),
                    lastStationId = null,
                ),
            notifications = NewsNotificationConfig(),
            savedArticleRecords = emptySet(),
        )
}
