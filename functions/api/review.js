// Cloudflare Pages Function: レビューアクションAPI
// POST /api/review → GitHub Actions workflow を トリガー

export async function onRequestPost(context) {
  const { request, env } = context;

  // CORS
  const headers = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
  };

  try {
    const body = await request.json();
    const { article_id, action, feedback } = body;

    if (!article_id || !action) {
      return new Response(JSON.stringify({ error: "article_id and action required" }), { status: 400, headers });
    }

    const GITHUB_TOKEN = env.GITHUB_TOKEN;
    if (!GITHUB_TOKEN) {
      return new Response(JSON.stringify({ error: "GITHUB_TOKEN not configured" }), { status: 500, headers });
    }

    // GitHub Actions workflow_dispatch をトリガー
    const resp = await fetch(
      "https://api.github.com/repos/yangpinggaoye15-dotcom/ai-tools-lab/actions/workflows/review-action.yml/dispatches",
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${GITHUB_TOKEN}`,
          "Accept": "application/vnd.github.v3+json",
          "User-Agent": "NexusAI-ReviewBot",
        },
        body: JSON.stringify({
          ref: "main",
          inputs: {
            article_id: article_id,
            action: action,  // "approve", "reject", "fix"
            feedback: feedback || "",
          },
        }),
      }
    );

    if (resp.status === 204) {
      return new Response(JSON.stringify({ success: true, message: `${action} action triggered` }), { headers });
    } else {
      const errText = await resp.text();
      return new Response(JSON.stringify({ error: `GitHub API error: ${resp.status}`, detail: errText }), { status: 500, headers });
    }
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500, headers });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
