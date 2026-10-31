// Frontend interactions - AI Campus Placement Agent

document.addEventListener("DOMContentLoaded", () => {
  initThemeToggle();
  initFormUpload();
  initCircularProgress();
  initMockInterview();
  initCompanyExplorer();
  initSkillGapFilter();
  initRoadmapExport();
});

function initThemeToggle() {
  const currentTheme = localStorage.getItem("theme") || "light";
  document.documentElement.setAttribute("data-bs-theme", currentTheme);

  const toggleBtns = document.querySelectorAll(".theme-toggle-btn");
  toggleBtns.forEach((btn) => {
    updateThemeIcon(btn, currentTheme);
    btn.addEventListener("click", () => {
      const activeTheme = document.documentElement.getAttribute("data-bs-theme");
      const newTheme = activeTheme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-bs-theme", newTheme);
      localStorage.setItem("theme", newTheme);
      toggleBtns.forEach((b) => updateThemeIcon(b, newTheme));
    });
  });
}

function updateThemeIcon(btn, theme) {
  if (theme === "dark") {
    btn.innerHTML = '<i class="fa-solid fa-sun text-warning"></i>';
    btn.title = "Switch to Light Mode";
  } else {
    btn.innerHTML = '<i class="fa-solid fa-moon text-secondary"></i>';
    btn.title = "Switch to Dark Mode";
  }
}

/**
 * Filter and search controls for the Skill Gap assessment table on the dashboard
 */
function initSkillGapFilter() {
  const searchInput = document.getElementById("skillSearchInput");
  const priorityFilter = document.getElementById("skillPriorityFilter");
  const table = document.getElementById("skillGapTable");
  const countBadge = document.getElementById("skillFilterCount");
  const emptyState = document.getElementById("skillGapEmptyState");

  if (!table || !searchInput || !priorityFilter) return;

  const rows = table.querySelectorAll("tbody tr.skill-gap-row");
  const totalRows = rows.length;

  function applyFilter() {
    const q = searchInput.value.toLowerCase().trim();
    const p = priorityFilter.value;
    let visibleCount = 0;

    rows.forEach((row) => {
      const skillName = (row.getAttribute("data-skill") || "").toLowerCase();
      const priority = (row.getAttribute("data-priority") || "").toLowerCase();
      const fullText = row.innerText.toLowerCase();

      const matchesSearch = !q || skillName.includes(q) || fullText.includes(q);
      const matchesPriority = p === "ALL" || priority === p.toLowerCase();

      if (matchesSearch && matchesPriority) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    });

    if (emptyState) {
      if (visibleCount === 0 && totalRows > 0) {
        emptyState.classList.remove("d-none");
      } else {
        emptyState.classList.add("d-none");
      }
    }

    if (countBadge) {
      if (q || p !== "ALL") {
        countBadge.innerText = `Showing ${visibleCount} of ${totalRows} Skills`;
      } else {
        countBadge.innerText = `${totalRows} Skills`;
      }
    }
  }

  searchInput.addEventListener("input", applyFilter);
  priorityFilter.addEventListener("change", applyFilter);

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && searchInput.value) {
      searchInput.value = "";
      applyFilter();
    }
  });
}

/**
 * Tracks interactive checklist tasks on the 6-Week Learning Roadmap
 * and persists completed task IDs in localStorage per analysis session.
 */
function initRoadmapTracker() {
  const container = document.getElementById("dashboardContainer");
  if (!container) return;

  const analysisId = container.getAttribute("data-analysis-id");
  if (!analysisId) return;

  const storageKey = `roadmap_tasks_${analysisId}`;
  let completedTasks = new Set();
  try {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      completedTasks = new Set(JSON.parse(saved));
    }
  } catch (e) {
    console.warn("Could not load roadmap progress from localStorage:", e);
  }

  const allCheckboxes = document.querySelectorAll(".roadmap-task-check");
  const weekCards = document.querySelectorAll(".week-card");
  const overallLabel = document.getElementById("overallRoadmapProgressLabel");
  const overallBar = document.getElementById("overallRoadmapProgressBar");

  function updateVisuals() {
    let totalAll = allCheckboxes.length;
    let checkedAll = 0;

    weekCards.forEach((card) => {
      const checksInWeek = card.querySelectorAll(".roadmap-task-check");
      let checkedInWeek = 0;
      checksInWeek.forEach((cb) => {
        if (cb.checked) checkedInWeek++;
      });

      const pct = checksInWeek.length > 0 ? Math.round((checkedInWeek / checksInWeek.length) * 100) : 0;
      const bar = card.querySelector(".week-progress-bar");
      const label = card.querySelector(".week-progress-label");
      if (bar) bar.style.width = `${pct}%`;
      if (label) label.innerText = `${pct}%`;

      checkedAll += checkedInWeek;
    });

    const overallPct = totalAll > 0 ? Math.round((checkedAll / totalAll) * 100) : 0;
    if (overallLabel) overallLabel.innerText = `${overallPct}%`;
    if (overallBar) overallBar.style.width = `${overallPct}%`;
  }

  allCheckboxes.forEach((cb) => {
    const taskId = cb.getAttribute("data-task-id");
    if (taskId && completedTasks.has(taskId)) {
      cb.checked = true;
      const span = cb.parentElement?.querySelector("span");
      if (span) span.style.textDecoration = "line-through";
    }

    cb.addEventListener("change", () => {
      const span = cb.parentElement?.querySelector("span");
      if (cb.checked) {
        if (taskId) completedTasks.add(taskId);
        if (span) span.style.textDecoration = "line-through";
      } else {
        if (taskId) completedTasks.delete(taskId);
        if (span) span.style.textDecoration = "none";
      }

      try {
        localStorage.setItem(storageKey, JSON.stringify(Array.from(completedTasks)));
      } catch (e) {
        console.warn("Failed saving roadmap task progress to localStorage:", e);
      }

      updateVisuals();
    });
  });

  updateVisuals();
}

function initCompanyExplorer() {
  const btn = document.getElementById("btnExploreCompany");
  const select = document.getElementById("companySelect");
  const modalEl = document.getElementById("companyModal");
  const modalBody = document.getElementById("companyModalBody");
  if (!btn || !select || !modalEl) return;

  btn.addEventListener("click", async () => {
    const company = select.value;
    if (!company || company === "General") {
      alert("Please select a specific company (e.g. Google, Microsoft, Amazon) to explore its hiring guide.");
      return;
    }
    const bsModal = new bootstrap.Modal(modalEl);
    modalBody.innerHTML = '<div class="text-center py-4"><span class="spinner-border text-primary" role="status"></span></div>';
    bsModal.show();

    try {
      const res = await fetch(`/api/company/${encodeURIComponent(company)}`);
      const data = await res.json();
      if (data.success && data.details) {
        const d = data.details;
        modalBody.innerHTML = `
          <h4 class="fw-bold text-primary mb-3">${data.company}</h4>
          <p class="text-secondary">${d.overview || ""}</p>
          <hr/>
          <h6 class="fw-bold"><i class="fa-solid fa-list-check text-primary me-2"></i>Hiring Process:</h6>
          <p class="small text-muted mb-3">${d.hiring_process || "N/A"}</p>
          <h6 class="fw-bold"><i class="fa-solid fa-laptop-code text-primary me-2"></i>Technical Rounds:</h6>
          <p class="small text-muted mb-3">${d.technical_rounds || "N/A"}</p>
          <h6 class="fw-bold"><i class="fa-solid fa-lightbulb text-warning me-2"></i>Preparation Tips:</h6>
          <div class="alert alert-light border small text-dark">${d.prep_tips || "N/A"}</div>
        `;
      } else {
        modalBody.innerHTML = `<div class="alert alert-warning">No details found for ${company}.</div>`;
      }
    } catch (err) {
      modalBody.innerHTML = '<div class="alert alert-danger">Error loading company details.</div>';
    }
  });
}

/**
 * Handlers for landing page upload forms & progress panel animations
 */
function initFormUpload() {
  const uploadForm = document.getElementById("analysisForm");
  if (!uploadForm) return;

  const fileInput = document.getElementById("resumeInput");
  const uploadArea = document.getElementById("uploadArea");
  const progressOverlay = document.getElementById("progressOverlay");
  const fileFeedbackBadge = document.getElementById("fileFeedbackBadge");
  const fileFeedbackBadgeText = document.getElementById("fileFeedbackBadgeText");
  const uploadTypeErrorAlert = document.getElementById("uploadTypeErrorAlert");
  const uploadTypeErrorMessage = document.getElementById("uploadTypeErrorMessage");
  const btnRemoveFile = document.getElementById("btnRemoveFile");
  const uploadIcon = document.getElementById("uploadIcon");
  const uploadPromptText = document.getElementById("uploadPromptText");
  const uploadSubText = document.getElementById("uploadSubText");

  // Format file size nicely
  const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  // Helper to validate and display feedback for chosen resume file
  const handleSelectedFile = (file) => {
    if (!file) return;

    const fileName = file.name || "";
    const lowerName = fileName.toLowerCase();
    const isPdf = lowerName.endsWith(".pdf");
    const isDocx = lowerName.endsWith(".docx");

    // Hide any previous error
    if (uploadTypeErrorAlert) {
      uploadTypeErrorAlert.classList.add("d-none");
    }

    if (!isPdf && !isDocx) {
      // Show explicit unsupported error alert
      if (uploadTypeErrorAlert && uploadTypeErrorMessage) {
        uploadTypeErrorMessage.textContent = `Unsupported file type "${fileName.split('.').pop() || 'unknown'}". Only .pdf and .docx resume files are supported.`;
        uploadTypeErrorAlert.classList.remove("d-none");
      }
      uploadArea.classList.add("border-danger");
      uploadArea.style.backgroundColor = "#fff8f8";
      // Clear input
      if (fileInput) fileInput.value = "";
      if (fileFeedbackBadge) fileFeedbackBadge.classList.add("d-none");
      return false;
    }

    // Success styling and visual feedback badge
    uploadArea.classList.remove("border-danger");
    uploadArea.style.borderColor = "var(--primary-blue)";
    uploadArea.style.backgroundColor = "var(--secondary-light)";

    const iconClass = isDocx ? "fa-file-word text-primary" : "fa-file-pdf text-danger";
    if (uploadIcon) {
      uploadIcon.className = `fa-solid ${iconClass} upload-icon`;
    }

    if (uploadPromptText) {
      uploadPromptText.innerHTML = `Ready for analysis: <b>${fileName}</b>`;
    }

    if (uploadSubText) {
      uploadSubText.textContent = `File size: ${formatFileSize(file.size)}`;
    }

    if (fileFeedbackBadge && fileFeedbackBadgeText) {
      fileFeedbackBadgeText.innerHTML = `<i class="fa-solid ${iconClass} me-1"></i> ${fileName} (${formatFileSize(file.size)})`;
      fileFeedbackBadge.classList.remove("d-none");
    }

    return true;
  };

  // Helper to reset upload area to clean default state
  const resetUploadArea = () => {
    if (fileInput) fileInput.value = "";
    if (uploadArea) {
      uploadArea.style.borderColor = "var(--border-color)";
      uploadArea.style.backgroundColor = "#ffffff";
      uploadArea.classList.remove("border-danger", "dragover-active");
    }
    if (uploadIcon) {
      uploadIcon.className = "fa-solid fa-cloud-arrow-up upload-icon";
    }
    if (uploadPromptText) {
      uploadPromptText.textContent = "Drag and drop your resume here, or click to browse";
    }
    if (uploadSubText) {
      uploadSubText.textContent = "Supports .pdf and .docx documents (max 10MB)";
    }
    if (fileFeedbackBadge) {
      fileFeedbackBadge.classList.add("d-none");
    }
    if (uploadTypeErrorAlert) {
      uploadTypeErrorAlert.classList.add("d-none");
    }
  };

  // Highlight upload area on drag events and file change
  if (uploadArea && fileInput) {
    uploadArea.addEventListener("click", (e) => {
      // Don't trigger browse if clicking the remove button
      if (e.target.closest("#btnRemoveFile")) return;
      fileInput.click();
    });

    if (btnRemoveFile) {
      btnRemoveFile.addEventListener("click", (e) => {
        e.stopPropagation();
        resetUploadArea();
      });
    }

    fileInput.addEventListener("change", () => {
      if (fileInput.files.length > 0) {
        handleSelectedFile(fileInput.files[0]);
      } else {
        resetUploadArea();
      }
    });

    ["dragenter", "dragover"].forEach(eventName => {
      uploadArea.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.add("dragover-active");
        uploadArea.style.borderColor = "var(--primary-blue)";
        uploadArea.style.backgroundColor = "var(--secondary-light)";
      }, false);
    });

    ["dragleave"].forEach(eventName => {
      uploadArea.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.remove("dragover-active");
        if (fileInput.files.length === 0) {
          uploadArea.style.borderColor = "var(--border-color)";
          uploadArea.style.backgroundColor = "#ffffff";
        }
      }, false);
    });

    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      uploadArea.classList.remove("dragover-active");
      const dt = e.dataTransfer;
      const files = dt ? dt.files : null;
      if (files && files.length > 0) {
        const file = files[0];
        const isValid = handleSelectedFile(file);
        if (isValid) {
          fileInput.files = files;
        }
      }
    });
  }

  // Intercept form submit to show animated Agent Progress panel
  uploadForm.addEventListener("submit", (e) => {
    const textInput = document.getElementById("resumeTextInput");
    const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
    const hasText = textInput && textInput.value.trim().length > 0;

    if (!hasFile && !hasText) {
      alert("Please upload a PDF or DOCX resume, or paste your resume text first.");
      e.preventDefault();
      return;
    }

    // Display progress overlay
    progressOverlay.classList.remove("d-none");

    const steps = [
      { id: "step1", delay: 0 },
      { id: "step2", delay: 1500 },
      { id: "step3", delay: 3200 },
      { id: "step4", delay: 4800 },
      { id: "step5", delay: 6500 },
      { id: "step6", delay: 8000 }
    ];

    // Trigger step updates sequentially
    steps.forEach((step, idx) => {
      setTimeout(() => {
        const element = document.getElementById(step.id);
        if (element) {
          element.classList.remove("text-muted");
          
          // Mark previous steps as completed
          if (idx > 0) {
            const prevElement = document.getElementById(steps[idx - 1].id);
            if (prevElement) {
              prevElement.classList.remove("active");
              prevElement.classList.add("completed");
              const indicator = prevElement.querySelector(".step-indicator");
              if (indicator) indicator.innerHTML = "✓";
            }
          }
          
          element.classList.add("active");
        }
      }, step.delay);
    });
  });
}

/**
 * Renders the circular SVG progress dials
 */
function initCircularProgress() {
  const circles = document.querySelectorAll(".circular-fill-ring");
  circles.forEach(circle => {
    const score = circle.getAttribute("data-score");
    if (score) {
      const radius = circle.r.baseVal.value;
      const circumference = 2 * Math.PI * radius;
      const offset = circumference - (score / 100) * circumference;
      
      // Animate circular transition
      setTimeout(() => {
        circle.style.strokeDasharray = `${circumference} ${circumference}`;
        circle.style.strokeDashoffset = offset;
      }, 300);
    }
  });
}

/**
 * Manages the live interactive mock interview simulation
 */
function initMockInterview() {
  const chatForm = document.getElementById("chatForm");
  if (!chatForm) return;

  const chatContainer = document.getElementById("chatContainer");
  const answerInput = document.getElementById("answerInput");
  const submitBtn = chatForm.querySelector("button[type='submit']");
  const evaluationPanel = document.getElementById("evaluationPanel");
  const btnMic = document.getElementById("btnMic");

  // Voice recording / speech recognition integration
  if (btnMic) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      btnMic.title = "Speech recognition not supported in this browser.";
      btnMic.style.opacity = "0.5";
    } else {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      let isRecording = false;

      btnMic.addEventListener("click", () => {
        if (!isRecording) {
          try {
            recognition.start();
            isRecording = true;
            btnMic.classList.remove("btn-outline-secondary");
            btnMic.classList.add("btn-danger");
            btnMic.innerHTML = '<i class="fa-solid fa-circle-stop"></i>';
          } catch (e) {
            console.warn(e);
          }
        } else {
          recognition.stop();
          isRecording = false;
          btnMic.classList.remove("btn-danger");
          btnMic.classList.add("btn-outline-secondary");
          btnMic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
        }
      });

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          answerInput.value = answerInput.value ? `${answerInput.value} ${transcript}` : transcript;
        }
      };

      recognition.onend = () => {
        isRecording = false;
        btnMic.classList.remove("btn-danger");
        btnMic.classList.add("btn-outline-secondary");
        btnMic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
      };

      recognition.onerror = () => {
        isRecording = false;
        btnMic.classList.remove("btn-danger");
        btnMic.classList.add("btn-outline-secondary");
        btnMic.innerHTML = '<i class="fa-solid fa-microphone"></i>';
      };
    }
  }

  // Live word counter and Ctrl+Enter keyboard submission
  if (answerInput) {
    const wordCountBadge = document.getElementById("wordCountBadge");
    answerInput.addEventListener("input", () => {
      const text = answerInput.value.trim();
      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      if (wordCountBadge) {
        wordCountBadge.innerText = `${words} word${words === 1 ? "" : "s"}`;
        if (words >= 30) {
          wordCountBadge.className = "text-success fw-bold";
        } else {
          wordCountBadge.className = "text-secondary fw-semibold";
        }
      }
    });

    answerInput.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        chatForm.requestSubmit();
      }
    });
  }

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const answer = answerInput.value.strip ? answerInput.value.strip() : answerInput.value.trim();
    if (!answer) {
      alert("Please enter a response before submitting.");
      return;
    }

    const questionIndex = parseInt(chatForm.getAttribute("data-question-index"));
    const analysisId = chatForm.getAttribute("data-analysis-id");

    // Disable UI inputs
    answerInput.disabled = true;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span>`;

    // Append user answer bubble to chat log
    appendChatBubble(answer, "user");
    answerInput.value = "";

    // Append loader bubble from Interview Agent
    const loaderBubble = appendChatBubble("<i>Interview Agent is evaluating your response...</i>", "agent");

    try {
      const response = await fetch(`/interview/${analysisId}/submit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest"
        },
        body: JSON.stringify({
          answer: answer,
          question_index: questionIndex
        })
      });

      const result = await response.json();
      loaderBubble.remove(); // Remove wait loading bubble

      if (result.error) {
        appendChatBubble(`Error: ${result.error}`, "agent");
        resetInputs();
        return;
      }

      // Display dynamic feedback scores on dashboard panels
      renderEvaluationDetails(result.evaluation, questionIndex + 1);

      // Append feedback bubble to chat log
      const feedbackText = `
        <b>Feedback:</b> ${result.evaluation.feedback}<br/>
        <b>Technical Accuracy:</b> ${result.evaluation.technical_accuracy}/100<br/>
        <b>Communication Score:</b> ${result.evaluation.communication_score}/100<br/>
        <b>Confidence Score:</b> ${result.evaluation.confidence_score}/100<br/>
        <b>Suggestions:</b><br/>
        <ul>
          ${result.evaluation.suggestions.map(s => `<li>${s}</li>`).join("")}
        </ul>
      `;
      appendChatBubble(feedbackText, "agent");

      if (result.completed) {
        appendChatBubble("<b>Congratulations! You have completed all mock interview questions.</b><br/>Please review your performance summary and export your transcript.", "agent");
        resetInputs(true); // Disable form inputs permanently
        document.getElementById("btnBackToDashboard")?.classList.remove("btn-outline-secondary");
        document.getElementById("btnBackToDashboard")?.classList.add("btn-primary");

        // Display completion modal if summary data is available
        if (result.summary) {
          showCompletionModal(result.summary);
        }
      } else {
        // Move to next question
        const nextQ = result.next_question;
        setTimeout(() => {
          appendChatBubble(`[<b>Question ${nextQ.index + 1} - ${nextQ.type}</b>]<br/>${nextQ.question}`, "agent");
          chatForm.setAttribute("data-question-index", nextQ.index);
          resetInputs();
        }, 1200);
      }

    } catch (err) {
      loaderBubble.remove();
      appendChatBubble("Could not evaluate response. Check your network connection or API configs.", "agent");
      resetInputs();
    }
  });

  function appendChatBubble(text, sender) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble chat-bubble-${sender} fade-in`;
    bubble.innerHTML = text;
    chatContainer.appendChild(bubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return bubble;
  }

  function resetInputs(disableAll = false) {
    answerInput.disabled = disableAll;
    submitBtn.disabled = disableAll;
    submitBtn.innerHTML = "Submit Answer";
  }

  function renderEvaluationDetails(evaluation, totalAnswered) {
    if (evaluationPanel) {
      evaluationPanel.classList.remove("d-none");
    }

    // Update gauges
    document.getElementById("confScore").innerText = `${evaluation.confidence_score}%`;
    document.getElementById("confBar").style.width = `${evaluation.confidence_score}%`;

    document.getElementById("commScore").innerText = `${evaluation.communication_score}%`;
    document.getElementById("commBar").style.width = `${evaluation.communication_score}%`;

    document.getElementById("techScore").innerText = `${evaluation.technical_accuracy}%`;
    document.getElementById("techBar").style.width = `${evaluation.technical_accuracy}%`;

    const totalQuestions = parseInt(chatForm.getAttribute("data-total-questions")) || 15;
    const progPercent = totalQuestions > 0 ? Math.round((totalAnswered / totalQuestions) * 100) : 0;
    document.getElementById("interviewProgressText").innerText = `${totalAnswered}/${totalQuestions} Questions Answered (${progPercent}%)`;
    document.getElementById("interviewProgressBar").style.width = `${progPercent}%`;
  }

  function showCompletionModal(summary) {
    const modalEl = document.getElementById("completionModal");
    if (!modalEl || typeof bootstrap === "undefined") return;

    const overallScoreEl = document.getElementById("modalOverallScore");
    const verdictBadge = document.getElementById("modalVerdictBadge");
    const feedbackEl = document.getElementById("modalSummaryFeedback");
    const hrScoreEl = document.getElementById("modalHrScore");
    const techScoreEl = document.getElementById("modalTechScore");
    const behScoreEl = document.getElementById("modalBehScore");

    if (overallScoreEl) overallScoreEl.innerText = summary.overall_score || "0";
    if (verdictBadge) verdictBadge.innerText = summary.readiness_verdict || "Completed";
    if (feedbackEl && summary.summary_feedback) feedbackEl.innerText = summary.summary_feedback;

    const cats = summary.category_scores || {};
    if (hrScoreEl && cats.HR) hrScoreEl.innerText = `${cats.HR.average_score}%`;
    if (techScoreEl && cats.Technical) techScoreEl.innerText = `${cats.Technical.average_score}%`;
    if (behScoreEl && cats.Behavioral) behScoreEl.innerText = `${cats.Behavioral.average_score}%`;

    const bsModal = new bootstrap.Modal(modalEl);
    bsModal.show();
  }
}

/**
 * Enables copying single-week roadmap tasks and exporting the complete 6-week
 * preparation schedule as a structured Markdown file for study notes or Notion.
 */
function initRoadmapExport() {
  const container = document.getElementById("dashboardContainer");
  if (!container) return;

  const companyName = container.getAttribute("data-company") || "Placement Target";

  // 1. Copy individual week tasks
  document.querySelectorAll(".copy-week-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      const card = btn.closest(".week-card");
      if (!card) return;

      const weekTitle = btn.getAttribute("data-week-name") || "Week";
      const hours = card.querySelector(".badge")?.innerText || "";
      let md = `### ${weekTitle} (${hours})\n\n`;

      const appendSection = (heading, selector) => {
        const items = card.querySelectorAll(selector);
        if (items.length > 0) {
          md += `#### ${heading}:\n`;
          items.forEach((item) => {
            const text = item.innerText.trim();
            if (text) md += `- [ ] ${text}\n`;
          });
          md += "\n";
        }
      };

      appendSection("Topics to Learn", ".roadmap-task-check[data-task-id*='_top_'] + span");
      appendSection("Coding Practice", ".roadmap-task-check[data-task-id*='_code_'] + span");
      appendSection("Micro Projects", ".roadmap-task-check[data-task-id*='_proj_'] + span");
      appendSection("Interview Prep Questions", ".roadmap-task-check[data-task-id*='_q_'] + span");

      const rev = card.querySelector(".border-top p")?.innerText.trim();
      if (rev) {
        md += `#### Revision Tasks:\n${rev}\n\n`;
      }

      try {
        await navigator.clipboard.writeText(md);
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-check text-success me-1"></i> Copied!';
        btn.classList.add("btn-success-subtle");
        setTimeout(() => {
          btn.innerHTML = originalHtml;
          btn.classList.remove("btn-success-subtle");
        }, 2000);
      } catch (err) {
        console.warn("Clipboard copy failed, fallback prompted:", err);
      }
    });
  });

  // 2. Export full 6-week study plan as a Markdown file
  const exportBtn = document.getElementById("btnExportRoadmapMarkdown");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      let fullMd = `# 6-Week Placement Preparation Roadmap\n`;
      fullMd += `**Target Company:** ${companyName}\n`;
      fullMd += `**Generated by:** AI Campus Placement Agent\n\n`;
      fullMd += `---\n\n`;

      document.querySelectorAll(".week-card").forEach((card) => {
        const title = card.querySelector("h5")?.innerText.trim() || "Week";
        const hours = card.querySelector(".badge")?.innerText.trim() || "";
        fullMd += `## ${title} (${hours})\n\n`;

        const appendSection = (heading, selector) => {
          const items = card.querySelectorAll(selector);
          if (items.length > 0) {
            fullMd += `### ${heading}:\n`;
            items.forEach((item) => {
              const text = item.innerText.trim();
              if (text) fullMd += `- [ ] ${text}\n`;
            });
            fullMd += "\n";
          }
        };

        appendSection("Topics to Learn", ".roadmap-task-check[data-task-id*='_top_'] + span");
        appendSection("Coding Practice Tasks", ".roadmap-task-check[data-task-id*='_code_'] + span");
        appendSection("Micro Projects", ".roadmap-task-check[data-task-id*='_proj_'] + span");
        appendSection("Interview Prep Questions", ".roadmap-task-check[data-task-id*='_q_'] + span");

        const rev = card.querySelector(".border-top p")?.innerText.trim();
        if (rev) {
          fullMd += `### Revision Tasks:\n${rev}\n\n`;
        }
        fullMd += `---\n\n`;
      });

      const blob = new Blob([fullMd], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Study_Plan_${companyName.replace(/[^a-zA-Z0-9_-]/g, "_")}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }
}
