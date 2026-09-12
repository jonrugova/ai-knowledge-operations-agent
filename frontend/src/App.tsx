import { FormEvent, useEffect, useRef, useState } from "react";
import "./App.css";

type Message = {
  id: number;
  role: "user" | "assistant";
  text: string;
  toolsUsed?: string[];
};

type ChatResponse = {
  answer: string;
  tools_used: string[];
};

type ApprovalStatus = "pending" | "approved" | "rejected";
type ExecutionStatus =
  | "pending"
  | "not_executed"
  | "executed"
  | "retry_required";

type Approval = {
  approval_id: string;
  approval_type: string;
  reason: string;
  user_request: string;
  requested_by?: string;
  status: ApprovalStatus;
  created_at: string;
  decided_at?: string;
  decided_by?: string;
  decision_note?: string;
  execution: Execution | null;
  execution_status: ExecutionStatus;
};

type Execution = {
  execution_id: string;
  action_type: string;
  status: "executed";
  executed_at: string;
};

type ApprovalDraft = {
  decisionNote: string;
};

type AuthUser = {
  username: string;
  role: "employee" | "approver";
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://localhost:8000" : "");

function App() {
  const [authLoading, setAuthLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [activeView, setActiveView] = useState<"chat" | "approvals">(
    new URLSearchParams(window.location.search).get("view") === "approvals"
      ? "approvals"
      : "chat",
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const nextMessageId = useRef(1);
  const messageEndRef = useRef<HTMLDivElement>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [approvalDrafts, setApprovalDrafts] = useState<
    Record<string, ApprovalDraft>
  >({});
  const [approvalsLoading, setApprovalsLoading] = useState(false);
  const [approvalsError, setApprovalsError] = useState("");
  const [submittingApprovalId, setSubmittingApprovalId] = useState("");

  useEffect(() => {
    const checkAuthentication = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Authentication check failed");
        }
        const data = (await response.json()) as {
          authenticated: boolean;
          username?: string;
          role?: AuthUser["role"];
        };
        setAuthenticated(data.authenticated);
        if (data.authenticated && data.username && data.role) {
          setCurrentUser({
            username: data.username,
            role: data.role,
          });
        }
      } catch {
        setAuthenticated(false);
      } finally {
        setAuthLoading(false);
      }
    };
    void checkAuthentication();
  }, []);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const addMessage = (
    role: Message["role"],
    text: string,
    toolsUsed?: string[],
  ) => {
    const message: Message = {
      id: nextMessageId.current,
      role,
      text,
      toolsUsed,
    };
    nextMessageId.current += 1;
    setMessages((current) => [...current, message]);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = input.trim();
    if (!message || isLoading) {
      return;
    }

    addMessage("user", message);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message }),
      });

      if (response.status === 401) {
        setAuthenticated(false);
        setCurrentUser(null);
        return;
      }
      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const data = (await response.json()) as ChatResponse;
      addMessage("assistant", data.answer, data.tools_used);
    } catch {
      addMessage(
        "assistant",
        "Something went wrong. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const clearConversation = () => {
    setMessages([]);
    setInput("");
  };

  const loadApprovals = async () => {
    setApprovalsLoading(true);
    setApprovalsError("");
    try {
      const response = await fetch(`${API_BASE_URL}/approvals`, {
        credentials: "include",
      });
      if (response.status === 401) {
        setAuthenticated(false);
        setCurrentUser(null);
        return;
      }
      if (response.status === 403) {
        setApprovalsError("Only approvers can review approval requests.");
        return;
      }
      if (!response.ok) {
        throw new Error("Approval request failed");
      }
      const records = (await response.json()) as Approval[];
      setApprovals(
        records.sort((left, right) => {
          if (left.status === right.status) {
            return right.created_at.localeCompare(left.created_at);
          }
          return left.status === "pending" ? -1 : 1;
        }),
      );
    } catch {
      setApprovalsError(
        "Approval requests could not be loaded. Please try again.",
      );
    } finally {
      setApprovalsLoading(false);
    }
  };

  useEffect(() => {
    if (authenticated && activeView === "approvals") {
      void loadApprovals();
    }
  }, [activeView, authenticated]);

  useEffect(() => {
    if (currentUser?.role !== "approver" && activeView === "approvals") {
      setActiveView("chat");
    }
  }, [activeView, currentUser]);

  const updateApprovalDraft = (
    approvalId: string,
    field: keyof ApprovalDraft,
    value: string,
  ) => {
    setApprovalDrafts((current) => ({
      ...current,
      [approvalId]: {
        ...(current[approvalId] ?? { decisionNote: "" }),
        [field]: value,
      },
    }));
  };

  const submitDecision = async (
    approvalId: string,
    decision: "approved" | "rejected",
  ) => {
    const draft = approvalDrafts[approvalId];
    if (!draft?.decisionNote.trim()) {
      setApprovalsError(
        "Enter a decision note before deciding.",
      );
      return;
    }

    setSubmittingApprovalId(approvalId);
    setApprovalsError("");
    try {
      const response = await fetch(
        `${API_BASE_URL}/approvals/${approvalId}/decision`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            decision,
            decision_note: draft.decisionNote,
          }),
        },
      );
      if (response.status === 401) {
        setAuthenticated(false);
        setCurrentUser(null);
        return;
      }
      if (response.status === 403) {
        setApprovalsError("You cannot decide this approval request.");
        return;
      }
      if (!response.ok) {
        throw new Error("Decision request failed");
      }
      setApprovalDrafts((current) => {
        const next = { ...current };
        delete next[approvalId];
        return next;
      });
      await loadApprovals();
    } catch {
      setApprovalsError(
        "The decision could not be saved. Refresh and try again.",
      );
    } finally {
      setSubmittingApprovalId("");
    }
  };

  const formatDate = (value: string) =>
    new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoginLoading(true);
    setLoginError("");
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        throw new Error("Login failed");
      }
      const data = (await response.json()) as {
        authenticated: boolean;
        username: string;
        role: AuthUser["role"];
      };
      setPassword("");
      setCurrentUser({
        username: data.username,
        role: data.role,
      });
      setAuthenticated(data.authenticated);
    } catch {
      setLoginError("Unable to sign in. Check the password and try again.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE_URL}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setAuthenticated(false);
      setCurrentUser(null);
      setMessages([]);
      setApprovals([]);
      setApprovalDrafts({});
      setPassword("");
      setUsername("");
    }
  };

  if (authLoading) {
    return (
      <main className="page-shell">
        <div className="auth-state">Checking authentication...</div>
      </main>
    );
  }

  if (!authenticated) {
    return (
      <main className="page-shell">
        <section className="login-card" aria-label="Sign in">
          <div className="login-mark" aria-hidden="true">
            AI
          </div>
          <p className="eyebrow">Secure access</p>
          <h1>AI Knowledge &amp; Operations Agent</h1>
          <p className="login-description">
            Sign in to access internal company knowledge, operational tools,
            and approval reviews.
          </p>
          <form className="login-form" onSubmit={handleLogin}>
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              disabled={loginLoading}
              required
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              disabled={loginLoading}
              required
            />
            {loginError && (
              <div className="login-error" role="alert">
                {loginError}
              </div>
            )}
            <button
              type="submit"
              disabled={!username.trim() || !password || loginLoading}
            >
              {loginLoading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <section
        className={`app-card ${activeView}`}
        aria-label="AI Knowledge and Operations Agent"
      >
        <header className="chat-header">
          <div>
            <p className="eyebrow">Developer portfolio project</p>
            <h1>AI Knowledge &amp; Operations Agent</h1>
            <p className="subtitle">
              Internal RAG-powered assistant for company knowledge,
              operational tools, and human-approved actions.
            </p>
          </div>
          <div className="header-actions">
          {activeView === "chat" && (
            <button
              className="clear-button"
              type="button"
              onClick={clearConversation}
              disabled={messages.length === 0 || isLoading}
            >
              Clear conversation
            </button>
          )}
            <button
              className="logout-button"
              type="button"
              onClick={() => void handleLogout()}
            >
              Logout
            </button>
          </div>
          {currentUser && (
            <div className="identity-indicator">
              Signed in as {currentUser.username} ·{" "}
              {currentUser.role === "approver" ? "Approver" : "Employee"}
            </div>
          )}
        </header>

        <nav className="view-tabs" aria-label="Application sections">
          <button
            className={activeView === "chat" ? "active" : ""}
            type="button"
            onClick={() => setActiveView("chat")}
          >
            Chat
          </button>
          {currentUser?.role === "approver" && (
            <button
              className={activeView === "approvals" ? "active" : ""}
              type="button"
              onClick={() => setActiveView("approvals")}
            >
              Approvals
            </button>
          )}
        </nav>

        {activeView === "chat" ? (
          <>
            <div className="message-area" aria-live="polite">
          {messages.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon" aria-hidden="true">
                AI
              </div>
              <h2>Support a customer or operational request</h2>
              <p>
                Ask about a customer request, company policy, delivery
                timeline, or operational decision.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <article
              className={`message-row ${message.role}`}
              key={message.id}
            >
              <div className="message-content">
                <span className="message-author">
                  {message.role === "user" ? "You" : "Agent"}
                </span>
                <div className="message-bubble">{message.text}</div>
                {message.role === "assistant" &&
                  message.toolsUsed &&
                  message.toolsUsed.length > 0 && (
                    <p className="tool-label">
                      Tools used: {message.toolsUsed.join(", ")}
                    </p>
                  )}
              </div>
            </article>
          ))}

          {isLoading && (
            <article className="message-row assistant">
              <div className="message-content">
                <span className="message-author">Agent</span>
                <div className="message-bubble thinking">
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  Thinking...
                </div>
              </div>
            </article>
          )}
              <div ref={messageEndRef} />
            </div>

            <form className="composer" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="chat-message">
            Message
          </label>
          <input
            id="chat-message"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask a question..."
            autoComplete="off"
            disabled={isLoading}
          />
          <button
            className="send-button"
            type="submit"
            disabled={!input.trim() || isLoading}
          >
            {isLoading ? "Sending..." : "Send"}
          </button>
            </form>
          </>
        ) : (
          <div className="approvals-screen">
            <div className="approvals-heading">
              <div>
                <h2>Human approval review</h2>
                <p>
                  Review protected requests. Approval releases the waiting
                  action through the protected backend gate.
                </p>
              </div>
              <button
                className="refresh-button"
                type="button"
                onClick={() => void loadApprovals()}
                disabled={approvalsLoading}
              >
                Refresh
              </button>
            </div>

            {approvalsError && (
              <div className="approval-error" role="alert">
                {approvalsError}
              </div>
            )}

            {approvalsLoading && approvals.length === 0 ? (
              <div className="approval-state">Loading approvals...</div>
            ) : approvals.length === 0 ? (
              <div className="approval-state">
                <h3>No approval requests</h3>
                <p>New protected requests will appear here.</p>
              </div>
            ) : (
              <div className="approval-list">
                {approvals.map((approval) => {
                  const draft = approvalDrafts[approval.approval_id] ?? {
                    decisionNote: "",
                  };
                  const isSubmitting =
                    submittingApprovalId === approval.approval_id;
                  return (
                    <article
                      className={`approval-card ${approval.status}`}
                      key={approval.approval_id}
                    >
                      <div className="approval-card-header">
                        <h3>{approval.approval_type}</h3>
                        <span className={`status ${approval.status}`}>
                          {approval.status}
                        </span>
                      </div>
                      <dl className="approval-details">
                        <div>
                          <dt>User request</dt>
                          <dd>{approval.user_request}</dd>
                        </div>
                        <div>
                          <dt>Reason</dt>
                          <dd>{approval.reason}</dd>
                        </div>
                        <div>
                          <dt>Created</dt>
                          <dd>{formatDate(approval.created_at)}</dd>
                        </div>
                        {approval.requested_by && (
                          <div>
                            <dt>Requested by</dt>
                            <dd>{approval.requested_by}</dd>
                          </div>
                        )}
                      </dl>

                      {approval.status === "pending" ? (
                        <div className="decision-form">
                          <label>
                            Decision note
                            <textarea
                              value={draft.decisionNote}
                              onChange={(event) =>
                                updateApprovalDraft(
                                  approval.approval_id,
                                  "decisionNote",
                                  event.target.value,
                                )
                              }
                              disabled={isSubmitting}
                            />
                          </label>
                          <div className="decision-actions">
                            <button
                              className="approve-button"
                              type="button"
                              onClick={() =>
                                void submitDecision(
                                  approval.approval_id,
                                  "approved",
                                )
                              }
                              disabled={isSubmitting}
                            >
                              Approve
                            </button>
                            <button
                              className="reject-button"
                              type="button"
                              onClick={() =>
                                void submitDecision(
                                  approval.approval_id,
                                  "rejected",
                                )
                              }
                              disabled={isSubmitting}
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      ) : (
                        <dl className="decision-summary">
                          <div>
                            <dt>Decided by</dt>
                            <dd>{approval.decided_by}</dd>
                          </div>
                          <div>
                            <dt>Decision note</dt>
                            <dd>{approval.decision_note}</dd>
                          </div>
                          {approval.decided_at && (
                            <div>
                              <dt>Decided</dt>
                              <dd>{formatDate(approval.decided_at)}</dd>
                            </div>
                          )}
                          <div>
                            <dt>Execution</dt>
                            <dd>
                              {approval.execution
                                ? "Executed"
                                : approval.execution_status ===
                                    "retry_required"
                                  ? "Retry required"
                                : "Not executed"}
                            </dd>
                          </div>
                          {approval.execution && (
                            <div>
                              <dt>Execution time</dt>
                              <dd>
                                {formatDate(
                                  approval.execution.executed_at,
                                )}
                              </dd>
                            </div>
                          )}
                        </dl>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

export default App;