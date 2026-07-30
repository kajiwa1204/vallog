"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";
import { startGitHubLogin } from "@/lib/auth";
import type { RepoOption, RepoOptionList, Project } from "@/types";
import styles from "./NewProjectModal.module.css";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function NewProjectModal({ open, onClose }: Props) {
  const router = useRouter();
  const [repos, setRepos] = useState<RepoOption[]>([]);
  const [privateAccess, setPrivateAccess] = useState(true);
  const [reposLoading, setReposLoading] = useState(false);
  const [reposError, setReposError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<RepoOption | null>(null);
  const [projectName, setProjectName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setRepos([]);
    setSearch("");
    setSelectedRepo(null);
    setProjectName("");
    setSubmitError(null);
    setReposError(null);

    setReposLoading(true);
    api
      .get<RepoOptionList>("/github/repos")
      .then((data) => {
        setRepos(data.repos);
        setPrivateAccess(data.private_access);
        setReposLoading(false);
      })
      .catch((e) => {
        setReposError(
          messageForError(e, { fallback: "リポジトリの取得に失敗しました" }),
        );
        setReposLoading(false);
      });
  }, [open]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return repos;
    return repos.filter((r) => r.full_name.toLowerCase().includes(q));
  }, [repos, search]);

  async function handleSubmit() {
    if (!selectedRepo) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const project = await api.post<Project>("/projects", {
        repo_owner: selectedRepo.owner,
        repo_name: selectedRepo.name,
        name: projectName.trim() || undefined,
      });
      router.push(`/projects/${project.id}/settings`);
    } catch (e) {
      setSubmitError(
        messageForError(e, {
          404: "リポジトリが見つからないか、アクセス権がありません",
          409: "このリポジトリはすでに登録されています",
          fallback: "登録に失敗しました",
        }),
      );
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="リポジトリを登録"
      footer={
        <div className={styles.footer}>
          {submitError && (
            <span className={styles.error}>{submitError}</span>
          )}
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={submitting}
          >
            キャンセル
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!selectedRepo || submitting}
            loading={submitting}
          >
            登録する
          </Button>
        </div>
      }
    >
      <div className={styles.body}>
        <Input
          label="リポジトリを検索"
          placeholder="owner/repo"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          id="repo-search"
        />

        {!reposLoading && !privateAccess && (
          <p className={styles.notice} role="status">
            privateリポジトリは表示されていません。表示するには
            <button
              type="button"
              className={styles.noticeLink}
              onClick={() => startGitHubLogin("/projects")}
            >
              GitHubで権限を再認可
            </button>
            してください。
          </p>
        )}

        <div className={styles.listWrap}>
          {reposLoading && (
            <div className={styles.center}>
              <Spinner label="リポジトリを取得中…" />
            </div>
          )}
          {reposError && (
            <p className={styles.error}>{reposError}</p>
          )}
          {!reposLoading && !reposError && filtered.length === 0 && (
            <p className={styles.empty}>該当するリポジトリがありません</p>
          )}
          {!reposLoading &&
            filtered.map((repo) => {
              const selected = selectedRepo?.full_name === repo.full_name;
              return (
                <button
                  key={repo.full_name}
                  className={`${styles.repoItem} ${selected ? styles.selected : ""}`}
                  onClick={() => setSelectedRepo(repo)}
                  type="button"
                >
                  <span className={`${styles.repoName} num`}>
                    {repo.full_name}
                  </span>
                  {repo.private && (
                    <Badge tone="neutral">private</Badge>
                  )}
                  {repo.fork && <Badge tone="ochre">fork</Badge>}
                </button>
              );
            })}
        </div>

        {selectedRepo?.fork && (
          <p className={styles.notice} role="alert">
            これはforkです。forkには上流リポジトリのPR・Issueが含まれないため、
            貢献がほとんど集計されません。チームで開発しているリポジトリを選んでください。
          </p>
        )}

        <Input
          label="プロジェクト名（任意）"
          placeholder={selectedRepo?.name ?? "リポジトリ名"}
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          id="project-name"
        />
      </div>
    </Modal>
  );
}
