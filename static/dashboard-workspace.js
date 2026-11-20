((root) => {
  function nextStep(update) {
    if (!update.branch) return 'Detached HEAD: select a branch before continuing.';
    if (update.worktree === 'changes') return 'Review uncommitted changes and stage only what belongs in your update.';
    if (update.worktree !== 'clean') return 'Working-tree status is unavailable; check it before continuing.';
    if (update.upstream.state === 'not_configured') return 'No upstream is configured. Review your branch and set an upstream when you push.';
    if (update.upstream.state === 'different') return 'Local and remote commits differ. Inspect divergence before pushing or pulling; this check cannot determine which is ahead.';
    if (update.upstream.state !== 'matches') return `Remote status needs attention: ${update.upstream.message || update.upstream.state}.`;
    const pr = update.pull_request;
    if (pr.state === 'unknown') return `Pull request status is unavailable: ${pr.message || 'check GitHub and retry'}.`;
    if (pr.state === 'none') return 'No same-repository pull request was found. Check GitHub before creating one.';
    if (pr.state === 'open' && !pr.head_matches) return `PR #${pr.number} has a different head commit. Verify the branch before merging.`;
    if (pr.state === 'open' && (pr.details_error || pr.draft === undefined)) return `PR #${pr.number} details are unavailable. Review it on GitHub before merging.`;
    if (pr.state === 'open' && pr.draft) return `PR #${pr.number} is a draft. Review it on GitHub when ready.`;
    if (pr.state === 'open') return `Review PR #${pr.number}, its approvals and required checks on GitHub.`;
    if (pr.state === 'merged' && pr.head_matches && pr.merged_head_matches && pr.merged_at && pr.merge_commit)
      return `PR #${pr.number} contains the verified merged commit. Fetch the base and start a fresh branch when ready.`;
    return `Latest same-repository PR is ${pr.state}; check GitHub before deciding what to do next.`;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {nextStep};
  if (!root.document) return;
  const document = root.document;
  const button = document.getElementById('mc-check-workspace');
  if (!button) return;
  const result = document.getElementById('mc-workspace-result');
  button.addEventListener('click', async () => {
    button.disabled = true;
    result.textContent = 'Checking local MasterChief and GitHub...';
    try {
      const response = await fetch('/sys/api/scm/update-check', {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      result.textContent = `MasterChief local repository · branch: ${data.branch || 'detached HEAD'} · commit: ${data.head.slice(0, 12)}. ${nextStep(data)} Checked ${new Date().toLocaleTimeString()}; refresh after changes. Fork-based PRs and ignored files are not included.`;
    } catch (error) {
      result.textContent = `Unable to check workspace: ${error.message}. Source Control admin access may be required.`;
    } finally { button.disabled = false; }
  });
  const tour = document.getElementById('mc-orientation');
  const tourStatus = document.getElementById('mc-tour-status');
  try { tour.open = root.localStorage.getItem('masterchief.tour.dismissed.v1') !== 'yes'; }
  catch { tourStatus.textContent = 'Browser storage is unavailable; tour dismissal cannot be saved.'; }
  document.getElementById('mc-dismiss-tour').addEventListener('click', () => {
    try { root.localStorage.setItem('masterchief.tour.dismissed.v1', 'yes'); tour.open = false; tour.querySelector('summary').focus(); }
    catch { tourStatus.textContent = 'Browser storage is unavailable; tour dismissal cannot be saved.'; }
  });
})(typeof window !== 'undefined' ? window : globalThis);
