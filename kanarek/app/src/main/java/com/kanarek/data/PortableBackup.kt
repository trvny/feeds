package com.kanarek.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.w3c.dom.Element
import org.w3c.dom.Node
import org.xml.sax.InputSource
import java.io.StringReader
import java.io.StringWriter
import java.nio.charset.StandardCharsets.UTF_8
import javax.xml.XMLConstants
import javax.xml.parsers.DocumentBuilderFactory
import javax.xml.transform.OutputKeys
import javax.xml.transform.TransformerFactory
import javax.xml.transform.dom.DOMSource
import javax.xml.transform.stream.StreamResult

internal data class PortableSettings(
    val feeds: List<String>,
    val backendUrl: String,
    val intervalSeconds: Int,
    val headlinesMode: Boolean,
    val offlineSavedArticles: Boolean,
    val perSourceCap: Int,
    val topSources: Set<String>,
    val stations: List<Station>,
    val favoriteStationIds: Set<String>,
    val lastStationId: String?,
    val backgroundRefreshMinutes: Int = ReaderBackgroundRefresh.OFF,
)

internal data class PortableBackup(
    val settings: PortableSettings,
    val notifications: NewsNotificationConfig,
    val savedArticleRecords: Set<String>,
)

internal data class BackupImportResult(
    val notificationEnabled: Boolean,
    val currentStation: Station?,
    val feedCount: Int,
    val stationCount: Int,
    val savedArticleCount: Int,
)

internal sealed class BackupException(message: String, cause: Throwable? = null) :
    IllegalArgumentException(message, cause)

internal class BackupTooLargeException : BackupException("Backup file is too large")

internal class BackupFormatException(message: String, cause: Throwable? = null) :
    BackupException(message, cause)

internal class BackupImportException(cause: Throwable) :
    BackupException("Backup import could not be committed", cause)

internal object PortableBackupCodec {
    const val MAX_FILE_BYTES = 4 * 1024 * 1024
    private const val VERSION = "1"
    private const val ROOT = "kanarek-backup"

    fun encode(input: PortableBackup): ByteArray {
        val backup = PortableBackupValidator.validate(input)
        val factory = secureDocumentBuilderFactory()
        val document = factory.newDocumentBuilder().newDocument()
        val root = document.createElement(ROOT).apply { setAttribute("version", VERSION) }
        document.appendChild(root)

        val settings = document.createElement("settings")
        settings.setAttribute("intervalSeconds", backup.settings.intervalSeconds.toString())
        settings.setAttribute(
            "backgroundRefreshMinutes",
            backup.settings.backgroundRefreshMinutes.toString(),
        )
        settings.setAttribute("headlinesMode", backup.settings.headlinesMode.toString())
        settings.setAttribute("offlineSavedArticles", backup.settings.offlineSavedArticles.toString())
        settings.setAttribute("perSourceCap", backup.settings.perSourceCap.toString())
        root.appendChild(settings)
        settings.appendValues(document, "feeds", backup.settings.feeds)
        settings.appendText(document, "backendUrl", backup.settings.backendUrl)
        settings.appendValues(document, "topSources", backup.settings.topSources.sorted())
        settings.appendText(document, "stationsM3u", M3uCodec.build(backup.settings.stations))
        settings.appendValues(
            document,
            "favoriteStationIds",
            backup.settings.favoriteStationIds.sorted(),
        )
        backup.settings.lastStationId?.let { settings.appendText(document, "lastStationId", it) }

        val notifications = document.createElement("notifications")
        notifications.setAttribute("enabled", backup.notifications.enabled.toString())
        notifications.setAttribute(
            "quietHoursEnabled",
            backup.notifications.quietHoursEnabled.toString(),
        )
        notifications.setAttribute(
            "quietStartMinute",
            backup.notifications.quietStartMinute.toString(),
        )
        notifications.setAttribute(
            "quietEndMinute",
            backup.notifications.quietEndMinute.toString(),
        )
        notifications.appendValues(
            document,
            "selectedFeeds",
            backup.notifications.selectedFeeds,
        )
        root.appendChild(notifications)

        val saved = document.createElement("savedArticles")
        backup.savedArticleRecords.sorted().forEach { record ->
            saved.appendText(document, "record", record)
        }
        root.appendChild(saved)

        val transformerFactory = TransformerFactory.newInstance()
        runCatching {
            transformerFactory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true)
        }
        val transformer =
            transformerFactory.newTransformer().apply {
                setOutputProperty(OutputKeys.ENCODING, UTF_8.name())
                setOutputProperty(OutputKeys.INDENT, "yes")
                setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "no")
            }
        val writer = StringWriter()
        transformer.transform(DOMSource(document), StreamResult(writer))
        val bytes = writer.toString().toByteArray(UTF_8)
        if (bytes.size > MAX_FILE_BYTES) throw BackupTooLargeException()
        return bytes
    }

    fun decode(bytes: ByteArray): PortableBackup {
        if (bytes.isEmpty()) throw BackupFormatException("Backup file is empty")
        if (bytes.size > MAX_FILE_BYTES) throw BackupTooLargeException()
        val document =
            try {
                secureDocumentBuilderFactory()
                    .newDocumentBuilder()
                    .parse(InputSource(StringReader(String(bytes, UTF_8))))
            } catch (error: Exception) {
                throw BackupFormatException("Backup XML is invalid", error)
            }
        val root = document.documentElement
        if (root == null || root.tagName != ROOT) {
            throw BackupFormatException("Not a Kanarek backup")
        }
        if (root.getAttribute("version") != VERSION) {
            throw BackupFormatException("Unsupported backup version")
        }

        val settingsElement = root.singleChild("settings")
        val feeds = settingsElement.values("feeds")
        val settings =
            PortableSettings(
                feeds = feeds,
                backendUrl = settingsElement.text("backendUrl"),
                intervalSeconds = settingsElement.requiredInt("intervalSeconds"),
                headlinesMode = settingsElement.requiredBoolean("headlinesMode"),
                offlineSavedArticles = settingsElement.requiredBoolean("offlineSavedArticles"),
                perSourceCap = settingsElement.requiredInt("perSourceCap"),
                topSources = settingsElement.values("topSources").toSet(),
                stations = M3uCodec.parse(settingsElement.text("stationsM3u")),
                favoriteStationIds =
                    settingsElement
                        .values("favoriteStationIds")
                        .toSet(),
                lastStationId =
                    settingsElement
                        .optionalText("lastStationId")
                        ?.takeIf(String::isNotBlank),
                backgroundRefreshMinutes =
                    settingsElement.optionalInt(
                        "backgroundRefreshMinutes",
                        ReaderBackgroundRefresh.OFF,
                    ),
            )

        val notificationElement = root.singleChild("notifications")
        val notifications =
            NewsNotificationConfig(
                enabled = notificationElement.requiredBoolean("enabled"),
                selectedFeeds = notificationElement.values("selectedFeeds"),
                configuredFeeds = feeds,
                quietHoursEnabled =
                    notificationElement.requiredBoolean("quietHoursEnabled"),
                quietStartMinute = notificationElement.requiredInt("quietStartMinute"),
                quietEndMinute = notificationElement.requiredInt("quietEndMinute"),
            )
        val savedRecords =
            root
                .singleChild("savedArticles")
                .directChildren("record")
                .mapTo(linkedSetOf()) { it.textContent.orEmpty() }

        return PortableBackupValidator.validate(
            PortableBackup(
                settings = settings,
                notifications = notifications,
                savedArticleRecords = savedRecords,
            ),
        )
    }

    private fun secureDocumentBuilderFactory(): DocumentBuilderFactory =
        DocumentBuilderFactory.newInstance().apply {
            isNamespaceAware = false
            isXIncludeAware = false
            isExpandEntityReferences = false
            setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true)
            setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
            setFeature("http://xml.org/sax/features/external-general-entities", false)
            setFeature("http://xml.org/sax/features/external-parameter-entities", false)
            runCatching {
                setFeature(
                    "http://apache.org/xml/features/nonvalidating/load-external-dtd",
                    false,
                )
            }
        }

    private fun Element.appendText(
        document: org.w3c.dom.Document,
        name: String,
        value: String,
    ) {
        appendChild(
            document.createElement(name).apply {
                appendChild(document.createTextNode(value))
            },
        )
    }

    private fun Element.appendValues(
        document: org.w3c.dom.Document,
        name: String,
        values: Iterable<String>,
    ) {
        val container = document.createElement(name)
        values.forEach { container.appendText(document, "value", it) }
        appendChild(container)
    }

    private fun Element.singleChild(name: String): Element {
        val matches = directChildren(name)
        if (matches.size != 1) throw BackupFormatException("Missing or duplicate $name section")
        return matches.single()
    }

    private fun Element.directChildren(name: String): List<Element> =
        buildList {
            for (index in 0 until childNodes.length) {
                val node = childNodes.item(index)
                if (node.nodeType == Node.ELEMENT_NODE && node.nodeName == name) {
                    add(node as Element)
                }
            }
        }

    private fun Element.values(name: String): List<String> =
        singleChild(name)
            .directChildren("value")
            .map { it.textContent.orEmpty() }

    private fun Element.text(name: String): String = singleChild(name).textContent.orEmpty()

    private fun Element.optionalText(name: String): String? {
        val matches = directChildren(name)
        if (matches.size > 1) throw BackupFormatException("Duplicate $name field")
        return matches.singleOrNull()?.textContent.orEmpty().takeIf { matches.isNotEmpty() }
    }

    private fun Element.requiredInt(name: String): Int =
        getAttribute(name).toIntOrNull()
            ?: throw BackupFormatException("Invalid $name value")

    private fun Element.optionalInt(
        name: String,
        default: Int,
    ): Int {
        val raw = getAttribute(name)
        return if (raw.isBlank()) default else raw.toIntOrNull()
            ?: throw BackupFormatException("Invalid $name value")
    }

    private fun Element.requiredBoolean(name: String): Boolean =
        getAttribute(name).toBooleanStrictOrNull()
            ?: throw BackupFormatException("Invalid $name value")
}

internal object PortableBackupValidator {
    fun validate(input: PortableBackup): PortableBackup {
        val feeds =
            input.settings.feeds
                .map(String::trim)
                .filter(String::isNotEmpty)
                .distinct()
        checkBackup(feeds.isNotEmpty() && feeds.size <= MAX_FEEDS, "Invalid feed list")
        feeds.forEach { feed ->
            checkBackup(feed.length <= MAX_URL_LENGTH && WebLinks.isHttpOrHttps(feed), "Invalid feed URL")
        }

        val backend = input.settings.backendUrl.trim()
        checkBackup(
            backend.length <= MAX_URL_LENGTH &&
                (backend.isBlank() || WebLinks.isHttpOrHttps(backend)),
            "Invalid backend URL",
        )
        checkBackup(input.settings.intervalSeconds in 3..120, "Invalid widget interval")
        checkBackup(
            input.settings.backgroundRefreshMinutes in ReaderBackgroundRefresh.options,
            "Invalid background refresh interval",
        )
        checkBackup(input.settings.perSourceCap in 0..20, "Invalid source cap")

        val topSources = normalizeSet(input.settings.topSources, MAX_TOP_SOURCES, MAX_SOURCE_LENGTH)
        val stations = input.settings.stations.distinctBy(Station::streamUrl)
        checkBackup(stations.size <= MAX_STATIONS, "Too many stations")
        val stationBytes = M3uCodec.build(stations).toByteArray(UTF_8).size
        checkBackup(stationBytes <= MAX_STATIONS_BYTES, "Station list is too large")
        stations.forEach { station ->
            checkBackup(
                station.name.length <= MAX_STATION_FIELD_LENGTH &&
                    station.streamUrl.isNotBlank() &&
                    station.streamUrl.length <= MAX_URL_LENGTH,
                "Invalid station",
            )
        }
        val stationIds = stations.mapTo(linkedSetOf(), Station::id)
        val favorites =
            normalizeSet(
                input.settings.favoriteStationIds,
                MAX_STATIONS,
                MAX_ID_LENGTH,
            ).filterTo(linkedSetOf()) { it in stationIds }
        val lastStationId = input.settings.lastStationId?.takeIf { it in stationIds }

        checkBackup(
            input.savedArticleRecords.size <= MAX_SAVED_ARTICLES,
            "Too many saved articles",
        )
        val decodedRecords =
            input.savedArticleRecords.map { raw ->
                checkBackup(raw.length <= MAX_SAVED_RECORD_LENGTH, "Saved article is too large")
                SavedArticleCodec.decodeRecord(raw)
                    ?: throw BackupFormatException("Invalid saved article")
            }
        val normalizedSaved =
            OfflineArticles
                .enforceLimit(
                    records = decodedRecords,
                    maxBytes = ArticleStateStore.OFFLINE_CONTENT_LIMIT_BYTES,
                ).mapTo(linkedSetOf(), SavedArticleCodec::encodeRecord)

        val selectedFeeds =
            input.notifications.selectedFeeds
                .map(String::trim)
                .filter { it in feeds }
                .distinct()
                .ifEmpty { if (input.notifications.enabled) feeds else emptyList() }
        val notifications =
            input.notifications
                .copy(
                    selectedFeeds = selectedFeeds,
                    configuredFeeds = feeds,
                ).normalized()
        checkBackup(
            notifications.quietStartMinute in 0 until NewsNotificationConfig.MINUTES_PER_DAY &&
                notifications.quietEndMinute in 0 until NewsNotificationConfig.MINUTES_PER_DAY,
            "Invalid quiet hours",
        )

        return PortableBackup(
            settings =
                input.settings.copy(
                    feeds = feeds,
                    backendUrl = backend,
                    topSources = topSources,
                    stations = stations,
                    favoriteStationIds = favorites,
                    lastStationId = lastStationId,
                    backgroundRefreshMinutes =
                        ReaderBackgroundRefresh.normalize(
                            input.settings.backgroundRefreshMinutes,
                        ),
                ),
            notifications = notifications,
            savedArticleRecords = normalizedSaved,
        )
    }

    private fun normalizeSet(
        values: Set<String>,
        maxCount: Int,
        maxLength: Int,
    ): Set<String> {
        val normalized =
            values
                .map(String::trim)
                .filter(String::isNotEmpty)
                .distinct()
        checkBackup(normalized.size <= maxCount, "Too many values")
        checkBackup(normalized.all { it.length <= maxLength }, "Value is too long")
        return normalized.toSet()
    }

    private fun checkBackup(
        condition: Boolean,
        message: String,
    ) {
        if (!condition) throw BackupFormatException(message)
    }

    private const val MAX_FEEDS = 100
    private const val MAX_URL_LENGTH = 2_048
    private const val MAX_TOP_SOURCES = 500
    private const val MAX_SOURCE_LENGTH = 200
    private const val MAX_STATIONS = 5_000
    private const val MAX_STATIONS_BYTES = 1024 * 1024
    private const val MAX_STATION_FIELD_LENGTH = 500
    private const val MAX_ID_LENGTH = 512
    private const val MAX_SAVED_ARTICLES = 2_000
    private const val MAX_SAVED_RECORD_LENGTH = 200_000
}

internal class PortableBackupManager(context: Context) {
    private val settings = SettingsStore(context.applicationContext)
    private val articles = ArticleStateStore(context.applicationContext)
    private val notifications = NewsNotificationStore(context.applicationContext)

    suspend fun exportBytes(): ByteArray =
        mutex.withLock {
            val backup =
                PortableBackup(
                    settings = settings.portableSnapshot(),
                    notifications = notifications.configNow(),
                    savedArticleRecords = articles.portableSavedRecordsNow(),
                )
            withContext(Dispatchers.Default) { PortableBackupCodec.encode(backup) }
        }

    suspend fun importBytes(bytes: ByteArray): BackupImportResult =
        mutex.withLock {
            val backup =
                withContext(Dispatchers.Default) {
                    PortableBackupCodec.decode(bytes)
                }
            val previousSettings = settings.portableSnapshot()
            val previousArticles = articles.portableSavedRecordsNow()
            val previousNotifications = notifications.snapshotState()
            withContext(NonCancellable) {
                try {
                    settings.replacePortable(backup.settings)
                    articles.replacePortableSavedRecords(backup.savedArticleRecords)
                    notifications.replacePortableConfig(backup.notifications)
                } catch (error: Exception) {
                    runCatching { notifications.restoreState(previousNotifications) }
                    runCatching { articles.replacePortableSavedRecords(previousArticles) }
                    runCatching { settings.replacePortable(previousSettings) }
                    throw BackupImportException(error)
                }
                val currentStation =
                    backup.settings.stations.firstOrNull {
                        it.id == backup.settings.lastStationId
                    } ?: backup.settings.stations.firstOrNull()
                BackupImportResult(
                    notificationEnabled = backup.notifications.enabled,
                    currentStation = currentStation,
                    feedCount = backup.settings.feeds.size,
                    stationCount = backup.settings.stations.size,
                    savedArticleCount = backup.savedArticleRecords.size,
                )
            }
        }

    private companion object {
        val mutex = Mutex()
    }
}
