import Foundation

struct Snapshot: Decodable {
    struct Totals: Decodable {
        let blocked: Int
        let inProgress: Int
        let todo: Int
        let done: Int

        private enum CodingKeys: String, CodingKey {
            case blocked
            case inProgress = "in_progress"
            case todo
            case done
        }
    }

    struct Repo: Decodable {
        let currentBranch: String
        let dirty: Bool
        let legacyLocalBranches: [String]

        private enum CodingKeys: String, CodingKey {
            case currentBranch = "current_branch"
            case dirty
            case legacyLocalBranches = "legacy_local_branches"
        }
    }

    struct ThreadItem: Decodable, Identifiable {
        struct Task: Decodable {
            let id: String
            let title: String
            let status: String
            let lineNo: Int

            private enum CodingKeys: String, CodingKey {
                case id
                case title
                case status
                case lineNo = "line_no"
            }
        }

        struct Log: Decodable {
            let timestamp: String
            let type: String
            let message: String
        }

        struct RuntimeStart: Decodable {
            let timestamp: String
            let message: String
            let lineNo: Int

            private enum CodingKeys: String, CodingKey {
                case timestamp
                case message
                case lineNo = "line_no"
            }
        }

        struct Branches: Decodable {
            struct Branch: Decodable, Identifiable {
                let name: String
                let worktree: String?
                var id: String { name }
            }

            let expectedPrefix: String
            let local: [Branch]
            let remote: [String]

            private enum CodingKeys: String, CodingKey {
                case expectedPrefix = "expected_prefix"
                case local
                case remote
            }
        }

        let thread: String
        let displayName: String
        let role: String
        let autoBranch: Bool
        let task: Task?
        let lastLog: Log?
        let runtimeStart: RuntimeStart?
        let branches: Branches

        var id: String { thread }

        private enum CodingKeys: String, CodingKey {
            case thread
            case displayName = "display_name"
            case role
            case autoBranch = "auto_branch"
            case task
            case lastLog = "last_log"
            case runtimeStart = "runtime_start"
            case branches
        }
    }

    let coordinationRoot: String
    let targetRepoRoot: String
    let generatedAt: String
    let repo: Repo
    let totals: Totals
    let threads: [ThreadItem]

    private enum CodingKeys: String, CodingKey {
        case coordinationRoot = "coordination_root"
        case targetRepoRoot = "target_repo_root"
        case generatedAt = "generated_at"
        case repo
        case totals
        case threads
    }

    var summaryText: String {
        """
        repo=\(targetRepoRoot)
        branch=\(repo.currentBranch)
        dirty=\(repo.dirty)
        blocked=\(totals.blocked) in_progress=\(totals.inProgress) todo=\(totals.todo) done=\(totals.done)
        """
    }
}
