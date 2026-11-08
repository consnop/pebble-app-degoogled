package coredevices.pebble.firmware

import com.anopticlabs.gravel.firmware.PebbleOsChangelogListSource
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.HttpRequestData
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import io.rebble.libpebblecommon.connection.FirmwareUpdateCheckResult
import io.rebble.libpebblecommon.metadata.WatchHardwarePlatform.CORE_OBELIX_PVT
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertContains
import kotlin.test.assertEquals
import kotlin.test.assertIs

/**
 * Pins the fork's patched-firmware feed: consnop/PebbleOS tags are `<upstream tag>-consnop-<patch id>`,
 * which compare equal to the upstream version, so a different build of the running version is offered
 * but the running build, or an older build of its version, never is.
 */
class GithubReleasesPatchedTest {

    private val board = "obelix_pvt"

    private fun release(tag: String, ageDays: Int, prerelease: Boolean = false, boards: List<String> = listOf(board)) =
        releaseJson(tag, ageDays, boards.map { normalAsset(it, tag, "sha256:" + "c".repeat(64), 100) }, prerelease = prerelease)

    private class Feed(body: String) {
        val requests = mutableListOf<HttpRequestData>()
        val client = HttpClient(MockEngine { request ->
            requests += request
            check(request.url.encodedPath == PATCHED_PATH) { "unexpected request to ${request.url}" }
            respond(body, HttpStatusCode.OK, headersOf(HttpHeaders.ContentType, "application/json"))
        }) {
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
        }
        val checker = GithubReleases(client, FirmwareArtifactExpectations(), PebbleOsChangelogListSource(client))
    }

    private suspend fun check(running: String, vararg releases: String, isRecovery: Boolean = false) =
        Feed(releaseList(*releases)).checker.getLatestPatchedFirmware(testWatchInfo(CORE_OBELIX_PVT, running, isRecovery))

    @Test
    fun offersThePatchedBuildOfTheRunningStockVersion() = runTest {
        val update = assertIs<FirmwareUpdateCheckResult.FoundUpdate>(check("v4.45.0", release("v4.45.0-consnop-bbbbbbbb", 1)))
        assertContains(update.url, "normal_${board}_v4.45.0-consnop-bbbbbbbb.pbz")
    }

    @Test
    fun neverReoffersTheRunningBuild() = runTest {
        assertEquals(
            FirmwareUpdateCheckResult.FoundNoUpdate,
            check("v4.45.0-consnop-bbbbbbbb", release("v4.45.0-consnop-bbbbbbbb", 1)),
        )
    }

    @Test
    fun neverOffersAnOlderBuildOfTheRunningVersion() = runTest {
        assertEquals(
            FirmwareUpdateCheckResult.FoundNoUpdate,
            check("v4.45.0-consnop-bbbbbbbb", release("v4.45.0-consnop-bbbbbbbb", 1), release("v4.45.0-consnop-aaaaaaaa", 3)),
        )
    }

    @Test
    fun offersANewerBuildOfTheRunningVersion() = runTest {
        val update = assertIs<FirmwareUpdateCheckResult.FoundUpdate>(
            check("v4.45.0-consnop-aaaaaaaa", release("v4.45.0-consnop-bbbbbbbb", 1), release("v4.45.0-consnop-aaaaaaaa", 3)),
        )
        assertContains(update.url, "v4.45.0-consnop-bbbbbbbb")
    }

    @Test
    fun prefersAHigherVersionAndSkipsUnusableReleases() = runTest {
        val update = assertIs<FirmwareUpdateCheckResult.FoundUpdate>(
            check(
                "v4.45.0",
                release("v4.47.0-consnop-dddddddd", 0, prerelease = true),
                release("v4.46.1-consnop-eeeeeeee", 0, boards = listOf("asterix")),
                release("v4.46.0-consnop-cccccccc", 2),
                release("v4.45.0-consnop-bbbbbbbb", 5),
            ),
        )
        assertContains(update.url, "v4.46.0-consnop-cccccccc")
    }

    @Test
    fun offersNothingOlderThanTheRunningVersion() = runTest {
        assertEquals(FirmwareUpdateCheckResult.FoundNoUpdate, check("v4.46.0", release("v4.45.0-consnop-bbbbbbbb", 1)))
    }

    @Test
    fun recoveryAlwaysGetsTheNewestBuild() = runTest {
        assertIs<FirmwareUpdateCheckResult.FoundUpdate>(
            check("v4.9.142", release("v4.45.0-consnop-bbbbbbbb", 1), isRecovery = true),
        )
    }

    @Test
    fun onlyThePatchedFeedIsAsked() = runTest {
        val feed = Feed(releaseList(release("v4.45.0-consnop-bbbbbbbb", 1)))
        feed.checker.getLatestPatchedFirmware(testWatchInfo(CORE_OBELIX_PVT, "v4.45.0"))
        assertEquals(listOf(PATCHED_PATH), feed.requests.map { it.url.encodedPath })
    }

    private companion object {
        const val PATCHED_PATH = "/repos/consnop/PebbleOS/releases"
    }
}
