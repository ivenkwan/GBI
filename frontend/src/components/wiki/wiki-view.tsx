"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MarkdownText } from "@/components/ui/markdown";
import {
  deleteWikiPage,
  getWikiHistory,
  getWikiPage,
  listWikiPages,
  restoreWikiPage,
  searchWiki,
  upsertWikiPage,
  type WikiPage,
  type WikiPageSummary,
  type WikiRevision,
  type WikiSearchHit,
} from "@/lib/api-client";
import { useAuth } from "@/components/auth/auth-provider";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { BookOpen, History, List, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useSelectionParam } from "@/hooks/use-selection-param";


interface TreeNode {
  slug: string;
  title: string;
  children: TreeNode[];
}

function buildTree(pages: WikiPageSummary[]): TreeNode[] {
  const bySlug = new Map<string, TreeNode>();
  for (const p of pages) bySlug.set(p.slug, { slug: p.slug, title: p.title, children: [] });
  const roots: TreeNode[] = [];
  for (const p of pages) {
    const node = bySlug.get(p.slug)!;
    const parent = p.parent_slug ? bySlug.get(p.parent_slug) : undefined;
    if (parent && parent !== node) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}

function TreeView({
  nodes,
  active,
  depth,
  onSelect,
}: {
  nodes: TreeNode[];
  active: string | null;
  depth: number;
  onSelect: (slug: string) => void;
}) {
  return (
    <ul className={depth > 0 ? "pl-3 border-l border-gray-100 ml-1" : ""}>
      {nodes.map((n) => (
        <li key={n.slug}>
          <button
            onClick={() => onSelect(n.slug)}
            className={`w-full text-left px-2 py-1 rounded text-sm truncate transition-colors ${
              active === n.slug
                ? "bg-brand-50 text-brand-700 font-medium"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            {n.title}
          </button>
          {n.children.length > 0 && (
            <TreeView nodes={n.children} active={active} depth={depth + 1} onSelect={onSelect} />
          )}
        </li>
      ))}
    </ul>
  );
}

function WikiSidebarContent({
  isEditor,
  query,
  onQueryChange,
  onSearch,
  hasPages,
  tree,
  activeSlug,
  onSelect,
  onNew,
}: {
  isEditor: boolean;
  query: string;
  onQueryChange: (query: string) => void;
  onSearch: () => void;
  hasPages: boolean;
  tree: TreeNode[];
  activeSlug: string | null;
  onSelect: (slug: string) => void;
  onNew: () => void;
}) {
  return (
    <>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Knowledge base
        </span>
        {isEditor && (
          <button
            onClick={onNew}
            title="New page"
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
          >
            <Plus className="w-4 h-4" />
          </button>
        )}
      </div>
      <div className="px-3 py-2 border-b border-gray-100">
        <div className="flex gap-1.5">
          <Input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSearch()}
            placeholder="Search…"
            className="text-xs"
          />
          <button
            onClick={onSearch}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
            title="Search"
          >
            <Search className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        {!hasPages && (
          <EmptyState
            variant="inline"
            title="No pages yet"
            description={isEditor ? " — write the first one." : "."}
          />
        )}
        <TreeView
          nodes={tree}
          active={activeSlug}
          depth={0}
          onSelect={onSelect}
        />
      </div>
    </>
  );
}

export function WikiView() {
  const { user } = useAuth();
  const isEditor = (user?.roles ?? []).includes("admin") || !!user?.platform_admin;

  const [pages, setPages] = useState<WikiPageSummary[]>([]);
  const [active, setActive] = useState<WikiPage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Editor state
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ slug: "", title: "", content: "", parent: "" });
  const [formError, setFormError] = useState("");

  // History
  const [history, setHistory] = useState<WikiRevision[] | null>(null);

  // Search
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<WikiSearchHit[] | null>(null);

  const [listOpen, setListOpen] = useState(false);
  const [selected, setSelected] = useSelectionParam("page");
  const activeSlug = active?.slug ?? null;

  const load = useCallback(async () => {
    try {
      setPages(await listWikiPages());
    } catch {
      setError("Failed to load pages");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const open = useCallback(
    async (slug: string, opts?: { silent?: boolean }) => {
      setListOpen(false);
      if (!opts?.silent) setError("");
      setHistory(null);
      setHits(null);
      setEditing(false);
      try {
        setActive(await getWikiPage(slug));
      } catch {
        // A stale deep link falls back to the default view with no error
        // banner; a sidebar/search click still surfaces the failure.
        if (opts?.silent) setSelected(null);
        else setError("Could not load page");
      }
    },
    [setSelected],
  );

  // Param → state: adopt a deep-linked page; invalid slugs fall back to the
  // default view silently (no error banner for a stale shared link). Only a
  // param change can trigger this effect — comparing against the latest slug
  // ref (not the state value in deps) keeps a click-driven state change
  // from re-firing it, which would ping-pong with the state → param effect.
  const activeSlugRef = useRef(activeSlug);
  activeSlugRef.current = activeSlug;
  useEffect(() => {
    if (!selected || selected === activeSlugRef.current) return;
    open(selected, { silent: true });
  }, [selected, open]);

  // State → param: selection changes (open, new page, save, delete, search)
  // sync the URL.
  useEffect(() => {
    if (selected === activeSlug) return;
    setSelected(activeSlug);
  }, [activeSlug, selected, setSelected]);

  const startNew = () => {
    setListOpen(false);
    setActive(null);
    setHistory(null);
    setHits(null);
    setEditing(true);
    setForm({ slug: "", title: "", content: "", parent: "" });
    setFormError("");
  };

  const startEdit = () => {
    if (!active) return;
    setEditing(true);
    setForm({
      slug: active.slug,
      title: active.title,
      content: active.content_md,
      parent: active.parent_slug ?? "",
    });
    setFormError("");
  };

  const save = async () => {
    if (!form.slug.trim() || !form.title.trim() || !form.content.trim() || busy) return;
    if (!/^[a-z0-9][a-z0-9-]{0,199}$/.test(form.slug)) {
      setFormError("Slug: lowercase letters, digits, hyphens");
      return;
    }
    setBusy(true);
    setFormError("");
    try {
      const saved = await upsertWikiPage(form.slug, {
        title: form.title,
        content_md: form.content,
        parent_slug: form.parent.trim() || null,
      });
      setEditing(false);
      setActive(saved);
      await load();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const tree = useMemo(() => buildTree(pages), [pages]);

  const runSearch = async () => {
    if (!query.trim()) return;
    setHistory(null);
    setEditing(false);
    setActive(null);
    setHits(await searchWiki(query.trim()));
  };

  const openHistory = async () => {
    if (!active) return;
    setHistory(await getWikiHistory(active.slug));
  };

  return (
    <div className="flex h-full bg-gray-50">
      {/* Sidebar: tree + search + new */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
        <WikiSidebarContent
          isEditor={isEditor}
          query={query}
          onQueryChange={setQuery}
          onSearch={runSearch}
          hasPages={pages.length > 0}
          tree={tree}
          activeSlug={active?.slug ?? null}
          onSelect={open}
          onNew={startNew}
        />
      </aside>

      <Sheet open={listOpen} onOpenChange={setListOpen} title="Pages">
        <div className="flex h-full flex-col">
          <WikiSidebarContent
            isEditor={isEditor}
            query={query}
            onQueryChange={setQuery}
            onSearch={runSearch}
            hasPages={pages.length > 0}
            tree={tree}
            activeSlug={active?.slug ?? null}
            onSelect={open}
            onNew={startNew}
          />
        </div>
      </Sheet>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0">
        <PageHeader
          title="Wiki"
          description="Tenant knowledge base — feeds the AI pipeline"
          icon={BookOpen}
          actions={
            <button
              type="button"
              onClick={() => setListOpen(true)}
              title="Pages list"
              className="md:hidden p-2 rounded-lg text-gray-600 transition-colors hover:bg-gray-100"
            >
              <List className="h-4 w-4" />
            </button>
          }
        />

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-5">
            {error && <Alert>{error}</Alert>}

            {/* Search results */}
            {hits && (
              <section className="space-y-3">
                <h2 className="text-sm font-semibold text-gray-900">
                  Results for “{query}” ({hits.length})
                </h2>
                {hits.map((h) => (
                  <button
                    key={h.slug}
                    onClick={() => open(h.slug)}
                    className="w-full text-left bg-white border border-gray-200 rounded-xl p-4 hover:border-gray-300"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900">{h.title}</span>
                      <span className="text-[10px] font-mono text-gray-400">{h.slug}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1 line-clamp-3">{h.chunk}</p>
                  </button>
                ))}
                {hits.length === 0 && <p className="text-sm text-gray-400">No hits.</p>}
              </section>
            )}

            {/* History */}
            {history && active && (
              <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
                <h2 className="text-sm font-semibold text-gray-900">
                  History — {active.title}
                </h2>
                <ul className="divide-y divide-gray-100">
                  {history.map((r) => (
                    <li key={r.version} className="flex items-center justify-between py-2">
                      <div>
                        <span className="text-sm text-gray-800">v{r.version}</span>
                        <span className="text-xs text-gray-400 ml-2">{r.title}</span>
                        <div className="text-[10px] text-gray-400">
                          {new Date(r.created_at).toLocaleString()}
                        </div>
                      </div>
                      {isEditor && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={async () => {
                            setBusy(true);
                            try {
                              const restored = await restoreWikiPage(active.slug, r.version);
                              setActive(restored);
                              setHistory(null);
                              await load();
                            } finally {
                              setBusy(false);
                            }
                          }}
                        >
                          Restore
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
                <Button variant="outline" size="sm" onClick={() => setHistory(null)}>
                  Close history
                </Button>
              </section>
            )}

            {/* Editor */}
            {editing && (
              <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
                <h2 className="text-sm font-semibold text-gray-900">
                  {active ? "Edit page" : "New page"}
                </h2>
                <div className="grid grid-cols-2 gap-2">
                  <Input
                    placeholder="slug (url id, e.g. qualified-pipeline)"
                    value={form.slug}
                    disabled={!!active}
                    onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase() })}
                  />
                  <Input
                    placeholder="parent slug (optional)"
                    value={form.parent}
                    onChange={(e) => setForm({ ...form, parent: e.target.value })}
                  />
                </div>
                <Input
                  placeholder="Title"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  <textarea
                    className="w-full h-72 font-mono text-xs border border-gray-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-brand-600"
                    placeholder="Markdown content…"
                    value={form.content}
                    onChange={(e) => setForm({ ...form, content: e.target.value })}
                    spellCheck={false}
                  />
                  <div className="h-72 overflow-y-auto border border-gray-200 rounded-lg p-3">
                    <MarkdownText>{form.content || "_preview_"}</MarkdownText>
                  </div>
                </div>
                {formError && <p className="text-xs text-red-600">{formError}</p>}
                <div className="flex gap-2">
                  <Button onClick={save} disabled={busy}>
                    {busy ? "Saving…" : "Save"}
                  </Button>
                  <Button variant="outline" onClick={() => setEditing(false)} disabled={busy}>
                    Cancel
                  </Button>
                </div>
              </section>
            )}

            {/* Viewer */}
            {active && !editing && !history && (
              <section className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">{active.title}</h2>
                    <p className="text-[11px] text-gray-400 font-mono">
                      {active.slug} · v{active.version ?? "?"} · updated{" "}
                      {new Date(active.updated_at).toLocaleString()}
                    </p>
                  </div>
                  {isEditor && (
                    <div className="flex gap-1">
                      <button
                        title="Edit"
                        onClick={startEdit}
                        className="p-2 rounded-lg hover:bg-gray-100 text-gray-400"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        title="History"
                        onClick={openHistory}
                        className="p-2 rounded-lg hover:bg-gray-100 text-gray-400"
                      >
                        <History className="w-4 h-4" />
                      </button>
                      <button
                        title="Delete page"
                        onClick={async () => {
                          if (busy) return;
                          setBusy(true);
                          try {
                            await deleteWikiPage(active.slug);
                            setActive(null);
                            await load();
                          } catch (e) {
                            setError(e instanceof Error ? e.message : "Delete failed");
                          } finally {
                            setBusy(false);
                          }
                        }}
                        className="p-2 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
                <div className="prose prose-sm max-w-none break-words">
                  <MarkdownText>{active.content_md}</MarkdownText>
                </div>
              </section>
            )}

            {/* Empty state */}
            {!active && !editing && !hits && !history && (
              <div className="text-center mt-24 space-y-2">
                <BookOpen className="w-10 h-10 text-gray-300 mx-auto" />
                <p className="text-sm text-gray-400">
                  Select a page, search, or{isEditor ? " write a new one." : " ask your admin to add content."}
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
