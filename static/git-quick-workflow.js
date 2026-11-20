(() => {
  const container = document.getElementById('quick-workflow');
  if (!container) return;
  container.innerHTML = `
    <details class="panel">
      <summary>Open quick guided Git workflow</summary>
      <p>One place to save, publish, check or create a pull request, merge, and start the next task. Each button selects a command; review its fields and preview, run it, confirm when asked, and check its output before continuing. Nothing runs when you open this guide.</p>
      <ol class="quick-steps">
        <li><strong>Inspect and stage.</strong> Save edits first and check the branch. Stage all includes tracked changes, deletions and non-ignored new files; choose individual paths instead if needed.
          <div><button type="button" data-guide-command="status">Check status</button> <button type="button" data-guide-command="stage_all">Stage all</button> <button type="button" data-guide-command="stage">Stage one path</button></div></li>
        <li><strong>Review and commit.</strong> Check the full staged list and diff for private data and unintended changes. A commit contains everything staged.
          <div><button type="button" data-guide-command="status">Review staged list</button> <button type="button" data-guide-command="staged_diff">Review staged diff</button> <button type="button" data-guide-command="commit">Commit</button></div></li>
        <li><strong>Push the commit.</strong> Use the current upstream, or set it on the first push. Pushing updates an existing PR for this branch but does not create one.
          <div><button type="button" data-guide-command="push">Push upstream</button> <button type="button" data-guide-command="push_upstream">Set upstream and push</button></div></li>
        <li><strong>Find or create the pull request.</strong> Look up the current branch first. If an open PR is returned, use its URL and number rather than creating a duplicate. If lookup fails, read the error; authentication or repository problems are not proof that no PR exists. Create a PR only after verifying one is needed and the intended base and head.
          <div><button type="button" data-guide-command="pr_view">Find current branch PR</button> <button type="button" data-guide-command="pr">Create PR</button></div></li>
        <li><strong>Review and merge.</strong> Check the PR number, target branch, changes, approvals, and required checks on GitHub. Then enter the PR number and confirm a merge commit. GitHub policies may block or queue the merge; inspect the result and verify it is merged before continuing.
          <div><button type="button" data-guide-command="pr_view">Check PR status</button> <button type="button" data-guide-command="pr_merge">Merge PR</button></div></li>
        <li><strong>Start the next task.</strong> After merge, check for uncommitted work, fetch origin, then create and switch to a uniquely named feature branch from the updated base, for example <code>origin/Masterchief4</code> (use your actual base). Or switch to an existing branch after checking its state.
          <div><button type="button" data-guide-command="status">Check work</button> <button type="button" data-guide-command="fetch">Fetch origin</button> <button type="button" data-guide-command="new_branch">Create and switch to new branch</button> <button type="button" data-guide-command="branches">List branches</button> <button type="button" data-guide-command="switch_branch">Switch to existing branch</button></div></li>
      </ol>
      <p class="warning"><strong>Branch best practice:</strong> This workflow does not delete your local or remote branches. Branches point to commits; they are not backups. GitHub repository settings can automatically delete a remote branch after merge. Clean up only deliberately after verifying the merge and any work still needed. Switching branches can carry uncommitted changes.</p>
      <p>Requires Source Control administrator access and configured Git/GitHub authentication. Commands operate on the MasterChief repository, not a repository selected in GitHub Integration.</p>
    </details>`;
})();
