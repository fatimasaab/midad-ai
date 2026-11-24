"use strict";

const $ = id => document.getElementById(id);

const state = {
    projectId: null,
    transcript: null,
    analysis: null,
    player: null,
    clipEnd: null,
    busy: false
};

function escapeHTML(value) {
    return String(value ?? "").replace(
        /[&<>"']/g,
        char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[char]
    );
}

function formatTime(seconds) {
    seconds = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(seconds / 60);
    const remaining = Math.floor(seconds % 60);

    return String(minutes).padStart(2, "0") +
        ":" + String(remaining).padStart(2, "0");
}

function message(text, type = "") {
    $("activity-message").textContent = text;
    $("activity-message").className = type;
}

async function api(url, options = {}) {
    const response = await fetch(url, options);

    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const error = new Error(
            typeof data.detail === "string"
                ? data.detail
                : `Request failed (${response.status})`
        );

        error.status = response.status;
        throw error;
    }

    return response.json();
}

async function optionalAPI(url) {
    try {
        return await api(url);
    } catch (error) {
        if (error.status === 404) return null;
        throw error;
    }
}

function updateControls() {
    $("transcription-mode").disabled =
        state.busy ||
        !state.projectId ||
        Boolean(state.transcript);

    $("browse-button").disabled = state.busy;
    $("load-project").disabled = state.busy;
    $("project-id-input").disabled = state.busy;

    $("transcribe-button").disabled =
        state.busy ||
        !state.projectId ||
        Boolean(state.transcript);

    $("analyze-button").disabled =
        state.busy ||
        !state.transcript ||
        Boolean(state.analysis);

    document.querySelectorAll(".review-form button")
        .forEach(button => {
            button.disabled = state.busy;
        });
}

async function runTask(task, loadingMessage) {
    if (state.busy) return;

    state.busy = true;
    updateControls();
    message(loadingMessage, "loading");

    try {
        await task();
    } catch (error) {
        message(error.message, "error");
        console.error(error);
    } finally {
        state.busy = false;
        updateControls();
    }
}

function resetPlayer() {
    for (const id of ["video-player", "audio-player"]) {
        const player = $(id);
        player.pause();
        player.removeAttribute("src");
        player.load();
        player.hidden = true;
    }

    state.player = null;
    state.clipEnd = null;

    $("media-placeholder").hidden = false;
    $("timeline-slider").disabled = true;
    $("timeline-slider").value = 0;
    $("current-time").textContent = "00:00";
    $("total-time").textContent = "00:00";
}

function resetProject() {
    resetPlayer();

    state.projectId = null;
    state.transcript = null;
    state.analysis = null;

    renderAll();
}

function configurePlayer(contentType) {
    resetPlayer();

    const isAudio = contentType.startsWith("audio/");
    const player = $(isAudio ? "audio-player" : "video-player");

    state.player = player;

    $("media-placeholder").hidden = true;

    player.hidden = false;
    player.src = `/api/media/${state.projectId}/preview`;
    player.load();
}

for (const id of ["video-player", "audio-player"]) {
    const player = $(id);

    player.addEventListener("loadedmetadata", () => {
        if (player !== state.player) return;

        if (Number.isFinite(player.duration)) {
            $("timeline-slider").max = player.duration;
            $("timeline-slider").disabled = false;
            $("total-time").textContent =
                formatTime(player.duration);
        }
    });

    player.addEventListener("timeupdate", () => {
        if (player !== state.player) return;

        const current = player.currentTime;

        $("timeline-slider").value = current;
        $("current-time").textContent = formatTime(current);

        document.querySelectorAll(".transcript-segment")
            .forEach(segment => {
                segment.classList.toggle(
                    "active",
                    current >= Number(segment.dataset.start) &&
                    current < Number(segment.dataset.end)
                );
            });

        if (
            state.clipEnd !== null &&
            current >= state.clipEnd
        ) {
            player.pause();
            state.clipEnd = null;
        }
    });

    player.addEventListener("error", () => {
        if (player !== state.player) return;

        message(
            "This browser cannot preview the source format. " +
            "Transcription and analysis are still available.",
            "error"
        );
    });
}

$("timeline-slider").addEventListener("input", event => {
    if (!state.player) return;

    state.clipEnd = null;
    state.player.currentTime = Number(event.target.value);
});

function seekTo(seconds) {
    if (!state.player || state.player.readyState < 1) {
        message("Media preview is not ready.", "error");
        return false;
    }

    state.clipEnd = null;
    state.player.currentTime = seconds;
    return true;
}

async function previewClip(clip) {
    if (!seekTo(clip.start)) return;

    state.clipEnd = clip.end;

    try {
        await state.player.play();

        document.querySelector(".media-panel")
            .scrollIntoView({ behavior: "smooth" });
    } catch (error) {
        state.clipEnd = null;
        message("Unable to play this recording.", "error");
    }
}

async function loadProject(projectId) {
    if (!/^[a-f0-9]{32}$/i.test(projectId)) {
        throw new Error("Enter a valid project ID.");
    }

    const sourceURL = `/api/media/${projectId}/preview`;

    // Request only the first byte to identify the media type.
    const source = await fetch(sourceURL, {
        headers: { Range: "bytes=0-0" }
    });

    if (!source.ok) {
        throw new Error("Project media was not found.");
    }

    const contentType =
        source.headers.get("content-type") || "";

    if (source.body) {
        await source.body.cancel();
    }

    const transcript = await optionalAPI(
        `/api/media/${projectId}/transcript`
    );

    const analysis = transcript
        ? await optionalAPI(
            `/api/editorial/${projectId}/analysis`
        )
        : null;

    resetProject();

    state.projectId = projectId;
    state.transcript = transcript;
    state.analysis = analysis;

    $("project-id-input").value = projectId;

    localStorage.setItem("midad-project", projectId);

    configurePlayer(contentType);
    renderAll();

    message("Project loaded successfully.", "success");
}

async function uploadFile(file) {
    if (!file) return;

    if (file.size > 500 * 1024 * 1024) {
        message("File exceeds the 500 MB limit.", "error");
        return;
    }

    await runTask(async () => {
        const formData = new FormData();
        formData.append("file", file);

        const result = await api("/api/media/upload", {
            method: "POST",
            body: formData
        });

        await loadProject(result.project_id);

        message(
            `${result.filename} uploaded successfully.`,
            "success"
        );
    }, "Uploading media...");
}

$("browse-button").addEventListener("click", () => {
    $("file-input").click();
});

$("file-input").addEventListener("change", event => {
    uploadFile(event.target.files[0]);
    event.target.value = "";
});

const dropZone = $("drop-zone");

dropZone.addEventListener("dragover", event => {
    event.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", event => {
    event.preventDefault();
    dropZone.classList.remove("dragover");

    if (!state.busy) {
        uploadFile(event.dataTransfer.files[0]);
    }
});

$("load-project").addEventListener("click", () => {
    const projectId = $("project-id-input").value.trim();

    runTask(
        () => loadProject(projectId),
        "Loading existing project..."
    );
});

$("transcribe-button").addEventListener("click", () => {
    runTask(async () => {
        state.transcript = await api(
            `/api/media/${state.projectId}/transcribe?mode=${$("transcription-mode").value}`,
            { method: "POST" }
        );

        renderAll();

        message(
            "Transcription completed successfully.",
            "success"
        );
    }, "Whisper is transcribing your recording...");
});

$("analyze-button").addEventListener("click", () => {
    runTask(async () => {
        state.analysis = await api(
            `/api/editorial/${state.projectId}/analyze`,
            { method: "POST" }
        );

        renderAll();

        message(
            "AI editorial analysis completed.",
            "success"
        );
    }, "Qwen is analyzing your transcript...");
});

function renderStats() {
    const transcript = state.transcript;
    const analysis = state.analysis;

    $("media-duration").textContent = transcript
        ? `${transcript.duration.toFixed(2)}s`
        : "—";

    $("transcription-time").textContent = transcript
        ? `${transcript.processing_time.toFixed(2)}s`
        : "—";

    $("analysis-time").textContent = analysis
        ? `${analysis.processing_time.toFixed(2)}s`
        : "—";

    $("clip-count").textContent = analysis
        ? analysis.clips.length
        : "—";

    $("project-status").textContent = analysis
        ? "Analysis complete"
        : transcript
        ? "Transcript ready"
        : state.projectId
        ? "Media imported"
        : "No active project";
}

function renderTranscript() {
    const container = $("transcript-content");
    const transcript = state.transcript;

    $("language-label").textContent = transcript
        ? transcript.language.toUpperCase()
        : "—";

    if (!transcript) {
        container.innerHTML =
            '<div class="empty-state">' +
            'Your timestamped transcript will appear here.' +
            '</div>';
        return;
    }

    container.innerHTML = transcript.segments.map(segment => {
        const words = segment.words || [];

        const content = words.length
            ? words.map(word => {
                const text = escapeHTML(word.word);

                if (word.confidence < 0.80) {
                    return `<span class="low-confidence"
                        title="Confidence: ${
                            (word.confidence * 100).toFixed(1)
                        }%">${text}</span>`;
                }

                return text;
            }).join(" ")
            : escapeHTML(segment.text);

        return `
            <div class="transcript-segment"
                data-start="${segment.start}"
                data-end="${segment.end}"
                data-segment-id="${segment.id}">

                <button class="timestamp"
                    data-seek="${segment.start}">
                    ${formatTime(segment.start)}
                </button>

                <div class="segment-body">
                    <div class="segment-text" dir="auto">
                        ${content}
                    </div>

                    ${segment.manually_corrected
                        ? '<span class="corrected-label">Manually corrected</span>'
                        : ''}
                </div>

                ${!state.analysis ? `
                    <button class="segment-edit"
                        data-edit="${segment.id}">
                        Edit
                    </button>
                ` : ''}
            </div>
        `;
    }).join("");

    container.querySelectorAll("[data-seek]")
        .forEach(button => {
            button.addEventListener("click", () => {
                seekTo(Number(button.dataset.seek));
            });
        });

    container.querySelectorAll("[data-edit]")
        .forEach(button => {
            button.addEventListener("click", () => {
                if (state.busy || state.analysis) return;
                editTranscriptSegment(Number(button.dataset.edit));
            });
        });
}

function editTranscriptSegment(segmentId) {
    const segment = state.transcript.segments.find(
        item => item.id === segmentId
    );

    if (!segment || state.busy || state.analysis) return;

    renderTranscript();

    const row = document.querySelector(
        `[data-segment-id="${segmentId}"]`
    );

    const body = row.querySelector(".segment-body");

    body.innerHTML = `
        <textarea class="segment-editor"
            dir="auto"></textarea>

        <div class="correction-actions">
            <button class="segment-edit cancel-correction">
                Cancel
            </button>
            <button class="segment-edit save-correction">
                Save correction
            </button>
        </div>
    `;

    const editor = body.querySelector("textarea");
    editor.value = segment.text;
    editor.focus();

    row.querySelector("[data-edit]").hidden = true;

    body.querySelector(".cancel-correction")
        .addEventListener("click", renderTranscript);

    body.querySelector(".save-correction")
        .addEventListener("click", () => {
            if (state.busy || state.analysis) return;

            const text = editor.value.trim();

            if (!text) {
                message("Corrected text cannot be empty.", "error");
                return;
            }

            runTask(async () => {
                state.transcript = await api(
                    `/api/correction/${state.projectId}/segments/${segmentId}`,
                    {
                        method: "PATCH",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({ text })
                    }
                );

                renderAll();

                message(
                    "Transcript correction saved.",
                    "success"
                );
            }, "Saving transcript correction...");
        });
}

function statusText(status) {
    return String(status || "pending_review")
        .replaceAll("_", " ");
}

function requiresScholarlyReview(clip) {
    return Boolean(
        clip.scholarly_review_required ||
        (clip.review_flags || []).some(
            flag => flag.type === "religious_reference"
        )
    );
}

function renderClipFlags(clip) {
    const flags = clip.review_flags || [];

    return `
        ${requiresScholarlyReview(clip) ? `
            <div class="scholarly-notice">
                <strong>Scholarly review required</strong>
                <p>Religious references detected or additional
                review requested. Export requires scholarly approval.</p>
            </div>
        ` : ""}

        <details class="clip-review-flags">
            <summary>Review flags (${flags.length})</summary>

            ${flags.length ? flags.map(flag => `
                <div class="flag-card">
                    <strong>${escapeHTML(
                        statusText(flag.type)
                    )}</strong>

                    <p>${escapeHTML(flag.message)}</p>

                    ${(flag.words || []).map(word => `
                        <p dir="auto">
                            ${escapeHTML(word.word)} —
                            ${(word.confidence * 100).toFixed(1)}%
                            confidence at ${formatTime(word.start)}
                        </p>
                    `).join("")}

                    ${flag.text ? `
                        <p dir="auto">
                            ${escapeHTML(flag.text)}
                        </p>
                    ` : ""}
                </div>
            `).join("") : `
                <p>No automatic flags detected.
                Human review is still required.</p>
            `}
        </details>
    `;
}

function renderClips() {
    const container = $("clip-list");
    const clips = state.analysis?.clips || [];

    if (!clips.length) {
        container.innerHTML = `
            <div class="empty-state">
                ${state.analysis
                    ? "No suitable clips were identified."
                    : "Generate editorial analysis to discover suggested clips."}
            </div>
        `;

        return;
    }

    container.innerHTML = clips.map(clip => `
        <article class="clip-card">
            <div class="clip-meta">
                <span>CLIP ${String(clip.id).padStart(2, "0")}</span>
                <span class="status-${escapeHTML(clip.status)}">
                    ${escapeHTML(statusText(clip.status))}
                </span>
            </div>

            <h3>${escapeHTML(clip.title)}</h3>

            <p>${escapeHTML(clip.description)}</p>

            <div class="clip-meta">
                <span>
                    ${formatTime(clip.start)} –
                    ${formatTime(clip.end)}
                </span>
                <span>${clip.duration.toFixed(2)}s</span>
            </div>

            <div class="clip-source">
                ${escapeHTML(clip.source_text)}
            </div>

            <p><strong>AI rationale:</strong>
                ${escapeHTML(clip.reason)}
            </p>

            <p><strong>Context note:</strong>
                ${escapeHTML(clip.context_note)}
            </p>

            ${renderClipFlags(clip)}

            <div class="clip-actions">
                <button class="button secondary"
                    data-preview="${clip.id}">
                    Preview clip
                </button>
            </div>

            <form class="review-form"
                data-clip-id="${clip.id}">

                <label>Review type</label>

                <select name="review_type">
                    <option value="editorial">
                        Editorial review
                    </option>

                    ${clip.editorial_status === "approved"
                        ? `<option value="scholarly">
                            Scholarly review
                           </option>`
                        : ""}
                </select>

                <label>Reviewer name</label>

                <input name="reviewer"
                    maxlength="100"
                    placeholder="Reviewer name"
                    required>

                <label>Review notes</label>

                <textarea name="notes"
                    maxlength="2000"
                    placeholder="Document accuracy and context checks."
                    required></textarea>

                <label>
                    <input type="checkbox"
                        name="require_scholarly"
                        ${requiresScholarlyReview(clip)
                            ? "checked disabled"
                            : ""}>
                    Require scholarly review
                </label>

                <div class="clip-actions">
                    <button type="submit"
                        value="approved"
                        class="button primary">
                        Approve
                    </button>

                    <button type="submit"
                        value="rejected"
                        class="button danger">
                        Reject
                    </button>
                </div>
            </form>
        </article>
    `).join("");

    container.querySelectorAll("[data-preview]")
        .forEach(button => {
            button.addEventListener("click", () => {
                const clip = clips.find(
                    item => item.id === Number(button.dataset.preview)
                );

                if (clip) previewClip(clip);
            });
        });

    container.querySelectorAll(".review-form")
        .forEach(form => {
            form.addEventListener("submit", event => {
                event.preventDefault();

                const decision = event.submitter?.value;

                if (!["approved", "rejected"].includes(decision)) {
                    return;
                }

                submitReview(form, decision);
            });
        });
}

async function submitReview(form, decision) {
    const fields = new FormData(form);
    const clipId = Number(form.dataset.clipId);

    const reviewer = String(fields.get("reviewer") || "").trim();
    const notes = String(fields.get("notes") || "").trim();

    if (!reviewer || !notes) {
        message("Reviewer name and notes are required.", "error");
        return;
    }

    await runTask(async () => {
        const updatedClip = await api(
            `/api/review/${state.projectId}/clips/${clipId}`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    review_type: fields.get("review_type"),
                    decision,
                    reviewer,
                    notes,
                    require_scholarly:
                        form.elements.require_scholarly.checked
                })
            }
        );

        state.analysis.clips = state.analysis.clips.map(
            clip => clip.id === clipId ? updatedClip : clip
        );

        renderAll();

        message("Review decision saved.", "success");
    }, "Saving review decision...");
}

function renderReview() {
    const flags = state.analysis?.review_flags || [];
    const clips = state.analysis?.clips || [];

    $("review-flags").innerHTML = flags.length
        ? flags.map(flag => `
            <div class="flag-card">
                <strong>${escapeHTML(statusText(flag.type))}</strong>
                <p>${escapeHTML(flag.message)}</p>

                ${(flag.words || []).map(word => `
                    <p>
                        ${escapeHTML(word.word)} —
                        ${(word.confidence * 100).toFixed(1)}%
                        confidence at ${formatTime(word.start)}
                    </p>
                `).join("")}

                ${flag.text
                    ? `<p>${escapeHTML(flag.text)}</p>`
                    : ""}
            </div>
        `).join("")
        : `<div class="empty-state">
            ${state.analysis
                ? "No automatic flags detected. Human review is still required."
                : "Review flags will appear after AI analysis."}
           </div>`;

    const history = clips.flatMap(clip =>
        (clip.review_history || []).map(event => ({
            ...event,
            clipId: clip.id
        }))
    );

    $("review-history").innerHTML = history.length
        ? `<h3>Review history</h3>` +
            history.map(event => `
                <div class="history-entry">
                    <strong>
                        ${escapeHTML(event.reviewer)}
                    </strong>

                    <p>
                        Clip ${event.clipId} ·
                        ${escapeHTML(event.review_type)} ·
                        ${escapeHTML(event.decision)}
                    </p>

                    <p>${escapeHTML(event.notes)}</p>

                    <p>${escapeHTML(
                        new Date(event.timestamp).toLocaleString()
                    )}</p>
                </div>
            `).join("")
        : "";
}


async function downloadExport(clipId, button) {
    const projectId = state.projectId;

    if (!projectId || button.disabled) return;

    const clip = state.analysis?.clips?.find(
        item => item.id === clipId
    );

    if (!clip || clip.export_allowed !== true) {
        return;
    }

    const status = button.parentElement.querySelector(
        ".export-status"
    );

    button.disabled = true;
    button.textContent = "Generating export...";
    status.textContent = "Preparing media and subtitles...";

    try {
        const response = await fetch(
            `/api/export/${projectId}/clips/${clipId}`,
            { method: "POST" }
        );

        if (!response.ok) {
            const error = await response.json().catch(
                () => ({})
            );

            throw new Error(
                typeof error.detail === "string"
                    ? error.detail
                    : `Export failed (${response.status})`
            );
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        const link = document.createElement("a");
        link.href = url;
        link.download = `midad-clip-${clipId}.zip`;

        document.body.appendChild(link);
        link.click();
        link.remove();

        setTimeout(() => URL.revokeObjectURL(url), 60000);

        status.textContent = "Export generated successfully.";
        status.style.color = "#8DC7A2";

    } catch (error) {
        status.textContent = error.message;
        status.style.color = "#F28B82";

    } finally {
        button.disabled = false;
        button.textContent = "Export clip";
    }
}

function renderExports() {
    const clips = state.analysis?.clips || [];

    const approved = clips.filter(
        clip => clip.export_allowed === true
    );

    $("export-list").innerHTML = approved.length
        ? approved.map(clip => `
            <div class="export-item">
                <strong>${escapeHTML(clip.title)}</strong>

                <p class="status-approved">
                    Approval requirements satisfied
                </p>

                <p>
                    Export package includes trimmed media,
                    SRT and VTT subtitles, and review metadata.
                </p>

                <button
                    class="button secondary export-button"
                    data-clip-id="${Number(clip.id)}">
                    Export clip
                </button>

                <p class="export-status" role="status"></p>
            </div>
        `).join("")
        : `<div class="empty-state">
            No approved clips available for export.
           </div>`;

    document.querySelectorAll(".export-button")
        .forEach(button => {
            button.addEventListener("click", () => {
                downloadExport(
                    Number(button.dataset.clipId),
                    button
                );
            });
        });
}

function renderAll() {
    renderStats();
    renderTranscript();
    renderClips();
    renderReview();
    renderExports();
    updateControls();
}

document.querySelectorAll(".nav-item").forEach(link => {
    link.addEventListener("click", () => {
        document.querySelectorAll(".nav-item")
            .forEach(item => item.classList.remove("active"));

        link.classList.add("active");
    });
});

renderAll();

const previousProject = localStorage.getItem("midad-project");

if (previousProject) {
    $("project-id-input").value = previousProject;
}
