/**
 * WattWise - Frontend Application Controller
 * Stateless in-memory architecture for Electricity Unit Planning
 */

// Application state held strictly in-memory
const state = {
  currentStep: 1,
  uploadedFiles: [],
  appliances: [], // [{ id, name, watts, hours_per_day, essential }]
  baselineUnits: 0,
  targetUnits: 0,
  planResult: null // { baseline_units, target_units, gap_units, items, explanation, tips }
};

// DOM Element References
const elements = {
  // Navigation & Badges
  backendStatusBadge: document.getElementById('backendStatusBadge'),
  backendStatusText: document.getElementById('backendStatusText'),
  notificationArea: document.getElementById('notificationArea'),
  stepIndicators: [
    document.getElementById('stepIndicator1'),
    document.getElementById('stepIndicator2'),
    document.getElementById('stepIndicator3'),
    document.getElementById('stepIndicator4')
  ],
  stepViews: [
    document.getElementById('step1View'),
    document.getElementById('step2View'),
    document.getElementById('step3View'),
    document.getElementById('step4View')
  ],

  // Step 1: Upload
  dropzone: document.getElementById('dropzone'),
  fileInput: document.getElementById('fileInput'),
  btnBrowseFiles: document.getElementById('btnBrowseFiles'),
  filePreviewContainer: document.getElementById('filePreviewContainer'),
  fileCountBadge: document.getElementById('fileCountBadge'),
  btnClearFiles: document.getElementById('btnClearFiles'),
  fileTagsWrapper: document.getElementById('fileTagsWrapper'),
  btnScanLabels: document.getElementById('btnScanLabels'),
  btnSkipManual: document.getElementById('btnSkipManual'),

  // Step 2: Inventory & Baseline
  appliancesTableBody: document.getElementById('appliancesTableBody'),
  btnAddApplianceRow: document.getElementById('btnAddApplianceRow'),
  liveBaselineUnits: document.getElementById('liveBaselineUnits'),
  tableSummaryUnits: document.getElementById('tableSummaryUnits'),
  btnBackToStep1: document.getElementById('btnBackToStep1'),
  btnProceedToGoal: document.getElementById('btnProceedToGoal'),

  // Step 3: Goal
  goalBaselineDisplay: document.getElementById('goalBaselineDisplay'),
  targetUnitsInput: document.getElementById('targetUnitsInput'),
  goalDeltaNotice: document.getElementById('goalDeltaNotice'),
  btnBackToStep2: document.getElementById('btnBackToStep2'),
  btnGeneratePlan: document.getElementById('btnGeneratePlan'),
  presetButtons: document.querySelectorAll('.btn-preset'),

  // Step 4: Plan Tuning
  targetStatusBadge: document.getElementById('targetStatusBadge'),
  planBaselineVal: document.getElementById('planBaselineVal'),
  planTargetVal: document.getElementById('planTargetVal'),
  planCurrentLiveVal: document.getElementById('planCurrentLiveVal'),
  planTotalSavedVal: document.getElementById('planTotalSavedVal'),
  planTableBody: document.getElementById('planTableBody'),
  llmExplanationText: document.getElementById('llmExplanationText'),
  llmTipsList: document.getElementById('llmTipsList'),
  btnBackToStep3: document.getElementById('btnBackToStep3'),
  btnConfirmPlan: document.getElementById('btnConfirmPlan'),

  // Summary Modal / Export
  summaryModal: document.getElementById('summaryModal'),
  btnCloseSummary: document.getElementById('btnCloseSummary'),
  summaryDateStamp: document.getElementById('summaryDateStamp'),
  summaryBannerTitle: document.getElementById('summaryBannerTitle'),
  summaryBannerSubtitle: document.getElementById('summaryBannerSubtitle'),
  summaryStatusBanner: document.getElementById('summaryStatusBanner'),
  sumBaseline: document.getElementById('sumBaseline'),
  sumTarget: document.getElementById('sumTarget'),
  sumConfirmed: document.getElementById('sumConfirmed'),
  sumSavings: document.getElementById('sumSavings'),
  summaryTableBody: document.getElementById('summaryTableBody'),
  summaryTipsList: document.getElementById('summaryTipsList'),
  btnDownloadJson: document.getElementById('btnDownloadJson'),
  btnPrintPlan: document.getElementById('btnPrintPlan'),
  btnRestartPlan: document.getElementById('btnRestartPlan')
};

// Utilities
function formatKwh(val) {
  return Number(val || 0).toFixed(2);
}

function calculateKwh(watts, hours) {
  return (Number(watts || 0) * Number(hours || 0) * 30.0) / 1000.0;
}

function showNotification(msg, type = 'error') {
  elements.notificationArea.className = `notification-container ${type}`;
  elements.notificationArea.innerHTML = `<span>${msg}</span><button type="button" class="btn-text" onclick="elements.notificationArea.style.display='none'">&times;</button>`;
  elements.notificationArea.style.display = 'flex';
  setTimeout(() => {
    elements.notificationArea.style.display = 'none';
  }, 6000);
}

// Navigation between steps
function setStep(stepNumber) {
  state.currentStep = stepNumber;

  elements.stepViews.forEach((view, idx) => {
    if (idx + 1 === stepNumber) {
      view.classList.add('active');
    } else {
      view.classList.remove('active');
    }
  });

  elements.stepIndicators.forEach((ind, idx) => {
    ind.classList.remove('active', 'completed');
    if (idx + 1 === stepNumber) {
      ind.classList.add('active');
    } else if (idx + 1 < stepNumber) {
      ind.classList.add('completed');
    }
  });

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Check Backend Health on load
async function checkBackendHealth() {
  try {
    const res = await fetch('/api/health');
    if (res.ok) {
      const data = await res.json();
      if (data.demo_mode) {
        elements.backendStatusText.textContent = 'Demo Mode (Fast Canned Data)';
      } else {
        elements.backendStatusText.textContent = `Ollama Online (${data.text_model || 'Local'})`;
      }
    } else {
      elements.backendStatusText.textContent = 'Backend Offline';
    }
  } catch (err) {
    elements.backendStatusText.textContent = 'Ready (Local)';
  }
}

// Step 1: File Upload & Drag-and-Drop Handlers
function setupUploadListeners() {
  elements.btnBrowseFiles.addEventListener('click', () => {
    elements.fileInput.click();
  });

  elements.dropzone.addEventListener('click', (e) => {
    if (e.target !== elements.btnBrowseFiles) {
      elements.fileInput.click();
    }
  });

  elements.dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.dropzone.classList.add('drag-over');
  });

  elements.dropzone.addEventListener('dragleave', () => {
    elements.dropzone.classList.remove('drag-over');
  });

  elements.dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelected(Array.from(e.dataTransfer.files));
    }
  });

  elements.fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFilesSelected(Array.from(e.target.files));
    }
  });

  elements.btnClearFiles.addEventListener('click', () => {
    state.uploadedFiles = [];
    elements.fileInput.value = '';
    renderFilePreviews();
  });

  elements.btnSkipManual.addEventListener('click', () => {
    if (state.appliances.length === 0) {
      // Provide starting sample row for manual entry
      state.appliances = [
        { id: 1, name: 'Air Conditioner', watts: 1500, hours_per_day: 6, essential: false },
        { id: 2, name: 'Refrigerator', watts: 150, hours_per_day: 24, essential: true },
        { id: 3, name: 'Ceiling Fan', watts: 75, hours_per_day: 12, essential: false }
      ];
    }
    renderAppliancesTable();
    setStep(2);
  });

  elements.btnScanLabels.addEventListener('click', handleExtractAppliances);
}

function handleFilesSelected(newFiles) {
  const imageFiles = newFiles.filter(f => f.type.startsWith('image/'));
  if (imageFiles.length === 0) {
    showNotification('Please select valid image files (JPG, PNG).', 'warning');
    return;
  }
  state.uploadedFiles = [...state.uploadedFiles, ...imageFiles];
  renderFilePreviews();
}

function renderFilePreviews() {
  const count = state.uploadedFiles.length;
  if (count > 0) {
    elements.filePreviewContainer.style.display = 'block';
    elements.fileCountBadge.textContent = `${count} image${count > 1 ? 's' : ''} selected`;
    elements.btnScanLabels.disabled = false;

    elements.fileTagsWrapper.innerHTML = state.uploadedFiles.map((f, i) => `
      <span class="file-tag">
        📷 ${escapeHtml(f.name)} (${(f.size / 1024).toFixed(1)} KB)
      </span>
    `).join('');
  } else {
    elements.filePreviewContainer.style.display = 'none';
    elements.btnScanLabels.disabled = true;
    elements.fileTagsWrapper.innerHTML = '';
  }
}

async function handleExtractAppliances() {
  const btn = elements.btnScanLabels;
  const spinner = btn.querySelector('.spinner');
  const btnText = btn.querySelector('.btn-text-content');

  btn.disabled = true;
  spinner.style.display = 'inline-block';
  btnText.textContent = 'Extracting Appliance Specs...';

  try {
    const formData = new FormData();
    state.uploadedFiles.forEach(file => {
      formData.append('images', file);
    });

    const response = await fetch('/api/extract', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Failed to extract appliances');
    }

    if (data.appliances && data.appliances.length > 0) {
      // Map extracted items into state with default hours and essentials
      state.appliances = data.appliances.map((item, idx) => {
        const lowerName = (item.name || '').toLowerCase();
        let defaultHours = 6;
        let isEssential = false;

        if (lowerName.includes('fridge') || lowerName.includes('refrigerator')) {
          defaultHours = 24;
          isEssential = true;
        } else if (lowerName.includes('iron')) {
          defaultHours = 1;
        } else if (lowerName.includes('washing')) {
          defaultHours = 1.5;
        } else if (lowerName.includes('fan')) {
          defaultHours = 10;
        }

        return {
          id: Date.now() + idx,
          name: item.name || `Appliance ${idx + 1}`,
          watts: Number(item.watts) || 100,
          hours_per_day: defaultHours,
          essential: isEssential
        };
      });

      renderAppliancesTable();
      setStep(2);
      showNotification(data.message || `Extracted ${data.appliances.length} appliances successfully!`, 'success');
    } else {
      showNotification(data.message || 'No appliances found. Switched to manual inventory.', 'warning');
      if (state.appliances.length === 0) {
        state.appliances = [
          { id: 1, name: 'Air Conditioner', watts: 1500, hours_per_day: 6, essential: false },
          { id: 2, name: 'Refrigerator', watts: 150, hours_per_day: 24, essential: true }
        ];
      }
      renderAppliancesTable();
      setStep(2);
    }
  } catch (err) {
    showNotification(`OCR notice: ${err.message}. You can manually enter details below.`, 'warning');
    if (state.appliances.length === 0) {
      state.appliances = [
        { id: 1, name: 'Air Conditioner', watts: 1500, hours_per_day: 6, essential: false },
        { id: 2, name: 'Refrigerator', watts: 150, hours_per_day: 24, essential: true }
      ];
    }
    renderAppliancesTable();
    setStep(2);
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
    btnText.textContent = 'Scan Labels & Extract';
  }
}

// Step 2: Inventory Table Management & Live Recalculations
function setupStep2Listeners() {
  elements.btnAddApplianceRow.addEventListener('click', () => {
    state.appliances.push({
      id: Date.now(),
      name: '',
      watts: 100,
      hours_per_day: 4,
      essential: false
    });
    renderAppliancesTable();
  });

  elements.btnBackToStep1.addEventListener('click', () => {
    setStep(1);
  });

  elements.btnProceedToGoal.addEventListener('click', () => {
    if (state.appliances.length === 0) {
      showNotification('Please add at least one appliance.', 'warning');
      return;
    }

    // Verify valid data
    for (const a of state.appliances) {
      if (!a.name.trim()) {
        showNotification('Please provide a name for all appliances.', 'warning');
        return;
      }
      if (a.watts <= 0) {
        showNotification(`Appliance "${a.name}" must have power > 0 Watts.`, 'warning');
        return;
      }
      if (a.hours_per_day < 0 || a.hours_per_day > 24) {
        showNotification(`Daily hours for "${a.name}" must be between 0 and 24.`, 'warning');
        return;
      }
    }

    updateBaselineCalculations();
    // Default target suggestion is 20% reduction
    const suggestedTarget = Math.max(10, Math.round(state.baselineUnits * 0.8));
    if (!state.targetUnits || state.targetUnits >= state.baselineUnits) {
      state.targetUnits = suggestedTarget;
    }
    elements.targetUnitsInput.value = state.targetUnits;
    elements.goalBaselineDisplay.textContent = formatKwh(state.baselineUnits);
    updateGoalDelta();

    setStep(3);
  });
}

function renderAppliancesTable() {
  if (state.appliances.length === 0) {
    elements.appliancesTableBody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">
          No appliances in inventory yet. Click "Add Appliance" to get started.
        </td>
      </tr>
    `;
    updateBaselineCalculations();
    return;
  }

  elements.appliancesTableBody.innerHTML = state.appliances.map((a, idx) => {
    const kwh = calculateKwh(a.watts, a.hours_per_day);
    return `
      <tr data-id="${a.id}">
        <td>
          <input type="text" class="table-input" value="${escapeHtml(a.name)}" placeholder="e.g. Living Room AC" onchange="updateApplianceRow(${idx}, 'name', this.value)">
        </td>
        <td>
          <input type="number" class="table-input num-input" value="${a.watts}" min="1" step="1" oninput="updateApplianceRow(${idx}, 'watts', this.value)">
        </td>
        <td>
          <input type="number" class="table-input num-input" value="${a.hours_per_day}" min="0" max="24" step="0.5" oninput="updateApplianceRow(${idx}, 'hours_per_day', this.value)">
        </td>
        <td style="text-align: center;">
          <input type="checkbox" class="checkbox-custom" ${a.essential ? 'checked' : ''} onchange="updateApplianceRow(${idx}, 'essential', this.checked)">
        </td>
        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;" class="row-kwh-display">
          ${formatKwh(kwh)} kWh
        </td>
        <td style="text-align: center;">
          <button type="button" class="btn-remove-row" title="Delete Appliance" onclick="removeApplianceRow(${idx})">
            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  updateBaselineCalculations();
}

window.updateApplianceRow = function(index, field, value) {
  if (!state.appliances[index]) return;

  if (field === 'watts') {
    state.appliances[index].watts = Math.max(0, Number(value) || 0);
  } else if (field === 'hours_per_day') {
    state.appliances[index].hours_per_day = Math.min(24, Math.max(0, Number(value) || 0));
  } else if (field === 'essential') {
    state.appliances[index].essential = Boolean(value);
  } else if (field === 'name') {
    state.appliances[index].name = String(value);
  }

  // Update specific row's monthly kWh display
  const row = elements.appliancesTableBody.querySelectorAll('tr')[index];
  if (row) {
    const kwhCell = row.querySelector('.row-kwh-display');
    if (kwhCell) {
      const kwh = calculateKwh(state.appliances[index].watts, state.appliances[index].hours_per_day);
      kwhCell.textContent = `${formatKwh(kwh)} kWh`;
    }
  }

  updateBaselineCalculations();
};

window.removeApplianceRow = function(index) {
  state.appliances.splice(index, 1);
  renderAppliancesTable();
};

function updateBaselineCalculations() {
  const total = state.appliances.reduce((sum, a) => {
    return sum + calculateKwh(a.watts, a.hours_per_day);
  }, 0);

  state.baselineUnits = Math.round(total * 100) / 100;
  elements.liveBaselineUnits.textContent = formatKwh(state.baselineUnits);
  elements.tableSummaryUnits.textContent = `${formatKwh(state.baselineUnits)} kWh / month`;
}

// Step 3: Goal Setting & AI Plan Generation
function setupStep3Listeners() {
  elements.btnBackToStep2.addEventListener('click', () => {
    setStep(2);
  });

  elements.targetUnitsInput.addEventListener('input', (e) => {
    state.targetUnits = Number(e.target.value) || 0;
    updateGoalDelta();
  });

  elements.presetButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const pct = Number(btn.getAttribute('data-pct')) || 10;
      const target = Math.max(1, Math.round(state.baselineUnits * (1 - pct / 100)));
      state.targetUnits = target;
      elements.targetUnitsInput.value = target;
      updateGoalDelta();
    });
  });

  elements.btnGeneratePlan.addEventListener('click', handleGeneratePlan);
}

function updateGoalDelta() {
  const baseline = state.baselineUnits;
  const target = state.targetUnits;
  const delta = baseline - target;

  if (target <= 0) {
    elements.goalDeltaNotice.innerHTML = `<span class="text-danger">Please enter a target greater than 0 kWh.</span>`;
    return;
  }

  if (delta <= 0) {
    elements.goalDeltaNotice.innerHTML = `
      <span class="text-success">Target is already &ge; current baseline (${formatKwh(baseline)} kWh). No reductions needed.</span>
    `;
  } else {
    const pct = ((delta / baseline) * 100).toFixed(1);
    elements.goalDeltaNotice.innerHTML = `
      <span>Requires saving <strong>${formatKwh(delta)} kWh</strong> per month (<strong>${pct}% reduction</strong>).</span>
    `;
  }
}

async function handleGeneratePlan() {
  if (state.targetUnits <= 0) {
    showNotification('Please enter a target units goal greater than 0.', 'warning');
    return;
  }

  const btn = elements.btnGeneratePlan;
  const spinner = btn.querySelector('.spinner');
  const btnText = btn.querySelector('.btn-text-content');

  btn.disabled = true;
  spinner.style.display = 'inline-block';
  btnText.textContent = 'Analyzing with Ollama...';

  try {
    const payload = {
      appliances: state.appliances.map(a => ({
        name: a.name,
        watts: a.watts,
        hours_per_day: a.hours_per_day,
        essential: a.essential
      })),
      target_units: state.targetUnits
    };

    const res = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Failed to generate plan');
    }

    state.planResult = data;
    renderPlanView();
    setStep(4);
  } catch (err) {
    showNotification(`Error generating plan: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
    btnText.textContent = 'Generate Reduction Plan';
  }
}

// Step 4: Plan Tuning & Real-time Client-Side Target Recalculation
function setupStep4Listeners() {
  elements.btnBackToStep3.addEventListener('click', () => {
    setStep(3);
  });

  elements.btnConfirmPlan.addEventListener('click', openSummaryModal);
}

function renderPlanView() {
  const plan = state.planResult;
  if (!plan) return;

  elements.planBaselineVal.textContent = `${formatKwh(plan.baseline_units)} kWh`;
  elements.planTargetVal.textContent = `${formatKwh(plan.target_units)} kWh`;

  elements.llmExplanationText.textContent = plan.explanation || 'Plan generated successfully.';
  elements.llmTipsList.innerHTML = (plan.tips || []).map(tip => `<li>${escapeHtml(tip)}</li>`).join('');

  elements.planTableBody.innerHTML = plan.items.map((item, idx) => {
    return `
      <tr data-plan-idx="${idx}">
        <td><strong>${escapeHtml(item.name)}</strong></td>
        <td style="font-family: var(--font-mono);">${item.watts} W</td>
        <td style="font-family: var(--font-mono);">${item.old_hours} hrs</td>
        <td>
          <input type="number" class="table-input num-input plan-hour-input" value="${item.new_hours}" min="0" max="24" step="0.5" oninput="updatePlanHours(${idx}, this.value)">
        </td>
        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;" class="item-saved-display text-success">
          ${formatKwh(item.units_saved)} kWh
        </td>
      </tr>
    `;
  }).join('');

  recalculateLivePlanTotals();
}

window.updatePlanHours = function(itemIdx, newHoursValue) {
  if (!state.planResult || !state.planResult.items[itemIdx]) return;

  const item = state.planResult.items[itemIdx];
  const parsedHours = Math.min(24, Math.max(0, Number(newHoursValue) || 0));
  item.new_hours = parsedHours;

  // Recalculate units saved for this specific appliance
  const oldKwh = calculateKwh(item.watts, item.old_hours);
  const newKwh = calculateKwh(item.watts, item.new_hours);
  item.units_saved = Math.max(0, Math.round((oldKwh - newKwh) * 100) / 100);

  // Update table row display
  const row = elements.planTableBody.querySelectorAll('tr')[itemIdx];
  if (row) {
    const savedCell = row.querySelector('.item-saved-display');
    if (savedCell) {
      savedCell.textContent = `${formatKwh(item.units_saved)} kWh`;
    }
  }

  recalculateLivePlanTotals();
};

function recalculateLivePlanTotals() {
  if (!state.planResult) return;

  const target = state.planResult.target_units;

  // Real-time calculation strictly in JS:
  // units = watts * new_hours * 30 / 1000
  let currentTotalKwh = 0;
  let totalSavedKwh = 0;

  state.planResult.items.forEach(item => {
    const kwh = calculateKwh(item.watts, item.new_hours);
    const oldKwh = calculateKwh(item.watts, item.old_hours);
    currentTotalKwh += kwh;
    totalSavedKwh += Math.max(0, oldKwh - kwh);
  });

  currentTotalKwh = Math.round(currentTotalKwh * 100) / 100;
  totalSavedKwh = Math.round(totalSavedKwh * 100) / 100;

  elements.planCurrentLiveVal.textContent = `${formatKwh(currentTotalKwh)} kWh`;
  elements.planTotalSavedVal.textContent = `${formatKwh(totalSavedKwh)} kWh`;

  // Dynamic green/red status badge against target
  const badge = elements.targetStatusBadge;
  if (currentTotalKwh <= target) {
    const surplus = (target - currentTotalKwh).toFixed(2);
    badge.className = 'status-pill-badge within-target';
    badge.innerHTML = `✓ Within Target (${surplus} kWh below budget)`;
  } else {
    const deficit = (currentTotalKwh - target).toFixed(2);
    badge.className = 'status-pill-badge exceeds-target';
    badge.innerHTML = `⚠ Exceeds Target by ${deficit} kWh`;
  }
}

// Step 5: Final Summary Screen & Export Handlers
function setupSummaryModalListeners() {
  elements.btnCloseSummary.addEventListener('click', () => {
    elements.summaryModal.style.display = 'none';
  });

  elements.btnDownloadJson.addEventListener('click', downloadPlanJson);
  elements.btnPrintPlan.addEventListener('click', () => {
    window.print();
  });

  elements.btnRestartPlan.addEventListener('click', () => {
    elements.summaryModal.style.display = 'none';
    setStep(1);
  });
}

function openSummaryModal() {
  if (!state.planResult) return;

  const plan = state.planResult;
  let finalKwh = 0;
  let totalSaved = 0;

  plan.items.forEach(item => {
    const kwh = calculateKwh(item.watts, item.new_hours);
    finalKwh += kwh;
    totalSaved += calculateKwh(item.watts, item.old_hours) - kwh;
  });

  finalKwh = Math.round(finalKwh * 100) / 100;
  totalSaved = Math.max(0, Math.round(totalSaved * 100) / 100);

  elements.summaryDateStamp.textContent = `Generated on ${new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}`;
  elements.sumBaseline.textContent = `${formatKwh(plan.baseline_units)} kWh`;
  elements.sumTarget.textContent = `${formatKwh(plan.target_units)} kWh`;
  elements.sumConfirmed.textContent = `${formatKwh(finalKwh)} kWh`;
  elements.sumSavings.textContent = `${formatKwh(totalSaved)} kWh`;

  // Status banner styling
  if (finalKwh <= plan.target_units) {
    elements.summaryStatusBanner.style.background = 'var(--success-bg)';
    elements.summaryStatusBanner.style.borderColor = 'var(--success-border)';
    elements.summaryBannerTitle.style.color = 'var(--success)';
    elements.summaryBannerTitle.textContent = '✓ Goal Achieved: Target Met';
    elements.summaryBannerSubtitle.textContent = `Your confirmed appliance schedule uses ${formatKwh(finalKwh)} kWh, within your ${formatKwh(plan.target_units)} kWh goal.`;
  } else {
    elements.summaryStatusBanner.style.background = 'var(--danger-bg)';
    elements.summaryStatusBanner.style.borderColor = 'var(--danger-border)';
    elements.summaryBannerTitle.style.color = '#f87171';
    elements.summaryBannerTitle.textContent = '⚠ Slightly Over Target';
    elements.summaryBannerSubtitle.textContent = `Confirmed schedule is ${formatKwh(finalKwh - plan.target_units)} kWh above target. Consider reducing additional hours on non-essential appliances.`;
  }

  // Summary breakdown table
  elements.summaryTableBody.innerHTML = plan.items.map(item => {
    const monthlyUnits = calculateKwh(item.watts, item.new_hours);
    return `
      <tr>
        <td><strong>${escapeHtml(item.name)}</strong></td>
        <td>${item.watts} W</td>
        <td>${item.old_hours} hrs / day</td>
        <td><span class="badge" style="color: var(--accent);">${item.new_hours} hrs / day</span></td>
        <td style="text-align: right; font-family: var(--font-mono); font-weight: 700;">${formatKwh(monthlyUnits)} kWh</td>
      </tr>
    `;
  }).join('');

  // Summary tips
  elements.summaryTipsList.innerHTML = (plan.tips || []).map(tip => `<li>${escapeHtml(tip)}</li>`).join('');

  elements.summaryModal.style.display = 'flex';
}

function downloadPlanJson() {
  if (!state.planResult) return;

  let confirmedTotalKwh = 0;
  const items = state.planResult.items.map(item => {
    const kwh = calculateKwh(item.watts, item.new_hours);
    confirmedTotalKwh += kwh;
    return {
      appliance: item.name,
      power_watts: item.watts,
      original_hours_per_day: item.old_hours,
      confirmed_hours_per_day: item.new_hours,
      monthly_kwh: Number(formatKwh(kwh)),
      units_saved_monthly: Number(formatKwh(item.units_saved))
    };
  });

  const exportData = {
    app: "WattWise",
    version: "1.0",
    created_at: new Date().toISOString(),
    baseline_monthly_kwh: state.planResult.baseline_units,
    target_monthly_kwh: state.planResult.target_units,
    confirmed_monthly_kwh: Number(formatKwh(confirmedTotalKwh)),
    total_savings_kwh: Number(formatKwh(state.planResult.baseline_units - confirmedTotalKwh)),
    appliances: items,
    ai_analysis: {
      explanation: state.planResult.explanation,
      tips: state.planResult.tips
    }
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `wattwise-electricity-plan-${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Initializer
document.addEventListener('DOMContentLoaded', () => {
  setupUploadListeners();
  setupStep2Listeners();
  setupStep3Listeners();
  setupStep4Listeners();
  setupSummaryModalListeners();
  checkBackendHealth();
});
