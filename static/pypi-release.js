(() => {
  const target = document.getElementById('pypi-deploy');
  if (!target) return;
  async function releaseApi(url, options = {}) {
    const response = await fetch(url, {credentials: 'same-origin', ...options});
    let data;
    try { data = await response.json(); }
    catch {
      if (response.status === 404) throw new Error('The PyPI release endpoint was not found. Restart MasterChief to load the latest changes, then sign in as an RBAC admin.');
      throw new Error(`Unexpected server response (HTTP ${response.status}). Sign in as an RBAC admin and restart MasterChief if the problem persists.`);
    }
    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  const section = document.createElement('section');
  section.className = 'panel pypi-panel';
  section.setAttribute('aria-labelledby', 'pypi-title');
  section.innerHTML = `
    <p class="pypi-kicker">PACKAGE RELEASE / GITHUB + PYPI</p>
    <h2 id="pypi-title">PYPI DEPLOY</h2>
    <p><strong>GitHub stores your source; PyPI distributes your package.</strong> Merging on GitHub does not publish to PyPI. The tag connects the package to the exact merged commit it was built from.</p>
    <p><strong>Each release:</strong> Change version &rarr; commit and push &rarr; merge PR &rarr; tag &rarr; dry run &rarr; publish &rarr; verify.</p>
    <div class="pypi-controls">
      <h3>Guided release: step by step</h3>
      <p><strong>1. Choose a new version.</strong> Start on a feature branch containing the latest merged changes. Load the working-copy version, then review the suggested next patch or enter your own unused version. For example, after <code>4.0.3</code> you might choose <code>4.0.4</code>. Saving edits only <code>setup.py</code> on this computer; it does not commit, push or publish.</p>
      <button id="pypi-version-load" type="button">Load current version</button>
      <p id="pypi-version-status" role="status" aria-live="polite">Load the version to begin.</p>
      <label for="pypi-version-input">New package version (for example 4.0.1)</label>
      <input id="pypi-version-input" placeholder="4.0.1" autocomplete="off" disabled>
      <button id="pypi-version-save" type="button" disabled>Save version to setup.py</button>
      <p>Check <a href="https://pypi.org/project/masterchief/#history" target="_blank" rel="noopener noreferrer">PyPI release history</a>: the suggestion does not check availability, and published versions cannot be overwritten.</p>
      <p><strong>2. Put the changes on GitHub.</strong> Use the <a href="#quick-workflow">Git workflow below</a> to stage and review the intended files (including <code>setup.py</code>), commit, and push your feature branch. Then create a pull request (PR) into <code>Masterchief4</code>, review it, and merge it. A PR can only include commits already pushed to GitHub: if it says &ldquo;No commits between&rdquo;, check the branch name and confirm your new commit was pushed. Keep private data and credentials out of the commit.</p>
      <p><strong>3. Tag the merged release.</strong> After merging, fetch origin using the Git workflow, then check the merged version and commit below. Confirm the version is the one you intend to publish. Create and push its matching tag: for example, version <code>4.0.4</code> uses tag <code>v4.0.4</code>. This marks a Git commit; it does not publish to PyPI.</p>
      <button id="pypi-preview" type="button">Check merged release</button>
      <p id="pypi-preview-result" role="status" aria-live="polite">Release not checked yet.</p>
      <label for="pypi-tag">Release tag (for example v1.2.3)</label>
      <input id="pypi-tag" placeholder="v1.2.3" autocomplete="off">
      <button id="pypi-create-tag" type="button" disabled>Create and push release tag</button>
      <p><strong>4. Practice with a dry run.</strong> This checks version availability and builds and validates the package from the tagged commit. It does not upload anything. Review the tagged source and package contents for private data before publishing.</p>
      <button id="pypi-dry-run" type="button">Run PyPI dry run</button>
      <p><strong>5. Publish to PyPI.</strong> After a successful dry run, confirm the public upload. The server uses the <code>TWINE_PASSWORD</code> token stored in <a href="/secrets">Vault</a>. Do not paste tokens into source code, Git history, or this form.</p>
      <button id="pypi-publish" type="button" disabled>Publish to PyPI</button>
      <p id="pypi-result" role="status" aria-live="polite">Enter a tag and run a dry run first. Requires Source Control admin access on a Windows server.</p>
      <p><strong>6. Verify and finish.</strong> Open the <a href="https://pypi.org/project/masterchief/" target="_blank" rel="noopener noreferrer">MasterChief page on PyPI</a> and check the version and both files (wheel and source distribution). If the upload fails, times out, or its outcome is uncertain, check PyPI before retrying. A command completion message alone is not independent verification.</p>
    </div>
    <details>
      <summary>Technical details and command-line alternative</summary>
      <p>The buttons run <code>PYPI_ONLY_DEPLOY.ps1</code> on the Windows MasterChief server using its Python environment and Vault. They require Source Control admin access, Git, network access, and <code>build</code> and <code>twine</code> in that environment. The script builds from the specified local tag, not uncommitted changes or necessarily your current checkout. If tag pushing fails, a local tag may remain; inspect local and remote tags before retrying.</p>
      <p>To run it in PowerShell instead, replace the example tag with your actual release tag:</p>
      <pre><code>.\\PYPI_ONLY_DEPLOY.ps1 -Tag v1.2.3 -DryRun
.\\PYPI_ONLY_DEPLOY.ps1 -Tag v1.2.3 -UseVault</code></pre>
      <p class="warning"><strong>Do not rely on the automatic workflow:</strong> The checked-in PyPI GitHub Actions workflow has an invalid first key; it must be repaired and tested before using it. If repaired, a GitHub published-release event is configured to publish separately, so avoid competing uploads.</p>
      <p>The PyPI-only script does not publish to Chocolatey. The separate <code>CHOCO_PYPI_DEPLOY.ps1</code> publishes Chocolatey first and is not atomic. Its Chocolatey builder currently uses <code>jbalestrine/masterchief</code> rather than this checkout's <code>jbalestrine/tf</code> origin; resolve that source mismatch before using it.</p>
    </details>`;
  target.append(section);
  const tagInput = section.querySelector('#pypi-tag');
  const dryRun = section.querySelector('#pypi-dry-run');
  const publish = section.querySelector('#pypi-publish');
  const result = section.querySelector('#pypi-result');
  const previewButton = section.querySelector('#pypi-preview');
  const previewResult = section.querySelector('#pypi-preview-result');
  const createTag = section.querySelector('#pypi-create-tag');
  const versionLoad = section.querySelector('#pypi-version-load');
  const versionSave = section.querySelector('#pypi-version-save');
  const versionInput = section.querySelector('#pypi-version-input');
  const versionStatus = section.querySelector('#pypi-version-status');
  let versionSnapshot = null;
  versionLoad.addEventListener('click', async () => {
    versionSnapshot = null; versionLoad.disabled = true; versionSave.disabled = true; versionInput.disabled = true;
    versionStatus.textContent = 'Loading working-copy version and branch...';
    try {
      const data = await releaseApi('/sys/api/scm/pypi-version');
      versionSnapshot = data; versionInput.value = data.suggested; versionInput.disabled = false;
      versionSave.disabled = !data.branch || data.branch === 'Masterchief4';
      versionStatus.textContent = `Working copy: ${data.current} · branch: ${data.branch || 'detached HEAD'} · suggested next patch: ${data.suggested}. ${versionSave.disabled ? 'Switch to a feature branch before saving.' : 'The suggestion is not saved yet. Review it and check PyPI for availability before saving.'}`;
    } catch (error) { versionStatus.textContent = `Unable to load version: ${error.message}`; }
    finally { versionLoad.disabled = false; }
  });
  versionSave.addEventListener('click', async () => {
    const version = versionInput.value.trim();
    if (!versionSnapshot || !/^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$/.test(version)) {
      versionStatus.textContent = 'Load the version and enter three numbers, such as 4.0.1.'; return;
    }
    if (!window.confirm(`Change setup.py on branch ${versionSnapshot.branch} from ${versionSnapshot.current} to ${version}?\n\nThis only edits the working copy. Review and commit the change before merging.`)) return;
    versionSave.disabled = true; versionLoad.disabled = true; versionInput.disabled = true;
    versionStatus.textContent = 'Saving the version to setup.py...';
    try {
      const data = await releaseApi('/sys/api/scm/pypi-version', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({version, confirmation: version, file_version: versionSnapshot.file_version, branch: versionSnapshot.branch})
      });
      versionStatus.textContent = `Saved setup.py: ${data.previous} → ${data.version} on ${data.branch}. Next: stage and review setup.py, commit, push, then create and merge the PR.`;
      versionSnapshot = null;
    } catch (error) {
      versionSnapshot = null;
      versionStatus.textContent = `Unable to save version: ${error.message}. Reload the current version before retrying.`;
    } finally { versionLoad.disabled = false; }
  });
  let verified = null, preview = null, busy = false;
  tagInput.addEventListener('input', () => {
    verified = null; publish.disabled = true;
    createTag.disabled = !preview || Boolean(preview.local_tag_commit || preview.remote_tag_exists) || tagInput.value.trim() !== preview.tag;
  });
  previewButton.addEventListener('click', async () => {
    preview = null; verified = null; createTag.disabled = true; publish.disabled = true;
    previewButton.disabled = true; dryRun.disabled = true; tagInput.disabled = true;
    previewResult.textContent = 'Checking the latest merged branch on origin...';
    try {
      const data = await releaseApi('/sys/api/scm/pypi-release-preview');
      preview = data; tagInput.value = data.tag;
      const exists = Boolean(data.local_tag_commit || data.remote_tag_exists);
      let tagNote = exists ? 'This tag already exists; it cannot be overwritten. Verify its target before using it, or merge a new version.' : 'This matching tag is not present locally or on origin.';
      if (data.local_tag_commit && data.local_tag_commit !== data.commit) tagNote = 'Warning: the existing local tag points to a different commit. Do not deploy it without verifying its target.';
      previewResult.textContent = `${data.base} · commit ${data.commit} · setup.py version ${data.version} · suggested tag ${data.tag}. ${tagNote} For a newer version, update and merge setup.py first.`;
      createTag.disabled = exists;
    } catch (error) { previewResult.textContent = `Unable to check merged release: ${error.message}`; }
    finally { previewButton.disabled = false; dryRun.disabled = false; tagInput.disabled = false; }
  });
  createTag.addEventListener('click', async () => {
    const tag = tagInput.value.trim();
    if (!preview || tag !== preview.tag) { previewResult.textContent = 'Check the merged release and use its matching version tag first.'; return; }
    if (!window.confirm(`Create and push ${tag} to origin for ${preview.base} commit ${preview.commit}?\n\nThis publishes a Git tag. Confirm the merged version and source first.`)) return;
    createTag.disabled = true; previewButton.disabled = true; dryRun.disabled = true; publish.disabled = true; tagInput.disabled = true;
    verified = null;
    previewResult.textContent = 'Creating the local tag and pushing it to origin...';
    try {
      const data = await releaseApi('/sys/api/scm/pypi-release-tag', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tag, expected_commit: preview.commit, confirmation: tag})
      });
      previewResult.textContent = `${data.message} ${data.tag} → ${data.commit}. Continue with the dry run.`;
    } catch (error) {
      previewResult.textContent = `Tag creation failed or its outcome is unconfirmed: ${error.message} Check the local and remote tags before retrying.`;
    } finally { preview = null; previewButton.disabled = false; dryRun.disabled = false; tagInput.disabled = false; }
  });
  async function run(mode) {
    const tag = tagInput.value.trim();
    if (!/^v[0-9]+\.[0-9]+\.[0-9]+$/.test(tag)) {
      result.textContent = 'Enter a semantic tag such as v1.2.3.';
      return;
    }
    if (mode === 'publish') {
      if (!verified || verified.tag !== tag) { result.textContent = 'Run a successful dry run for this tag first.'; return; }
      if (!window.confirm(`Publish masterchief from ${tag} (commit ${verified.commit}) to PyPI?\n\nThis is a public, irreversible package release. Verify the tag, version and contents first.`)) return;
    } else { verified = null; }
    busy = true; dryRun.disabled = true; publish.disabled = true; tagInput.disabled = true; previewButton.disabled = true; createTag.disabled = true;
    result.textContent = mode === 'dry_run' ? 'Running dry run on the server; no package will be uploaded...' : 'Publishing to PyPI. Do not retry until the outcome is known...';
    try {
      const data = await releaseApi('/sys/api/scm/pypi-deploy', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tag, mode, confirmation: mode === 'publish' ? tag : null,
          expected_commit: mode === 'publish' ? verified.commit : null})
      });
      if (mode === 'dry_run') {
        verified = {tag: data.tag, commit: data.commit};
        result.textContent = `Dry run succeeded for ${data.tag}, commit ${data.commit}. Nothing was uploaded. Review the tagged source and package contents, then use Publish to PyPI.`;
      } else {
        verified = null;
        result.textContent = `Publish command completed for ${data.tag}, commit ${data.commit}. Open PyPI in step 6 and verify the version and both artifacts. If they are present, your release is complete; do not publish again.`;
      }
    } catch (error) {
      verified = null;
      result.textContent = `Release action failed or its outcome is unconfirmed: ${error.message}. Check PyPI before retrying a publish.`;
    } finally { busy = false; dryRun.disabled = false; tagInput.disabled = false; previewButton.disabled = false; createTag.disabled = !preview || Boolean(preview.local_tag_commit || preview.remote_tag_exists) || tag !== preview.tag; publish.disabled = busy || !verified; }
  }
  dryRun.addEventListener('click', () => run('dry_run'));
  publish.addEventListener('click', () => run('publish'));
  previewButton.click();
})();
