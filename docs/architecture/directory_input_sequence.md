# Directory Input Sequence

This document captures the clean-architecture interactions required to ingest
either a single file or a directory tree when invoking the Critique Council CLI.
The goal is to make dependency flow explicit so that the presentation layer never
reaches into infrastructure details directly.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as Presentation.CLI Parser
    participant Service as Application.CritiqueService
    participant RepoFactory as Application.RepositorySelector
    participant Repository as Infrastructure.ContentRepository
    participant Pipeline as Application.PipelineOrchestrator

    User->>CLI: run_critique --input-dir ...
    CLI->>Service: CritiqueRequestDTO
    Service->>RepoFactory: select_repository(request)
    RepoFactory-->>Service: DirectoryContentRepository
    Service->>Repository: load_input()
    Repository->>Repository: enumerate/filter/order files
    Repository-->>Service: PipelineInput
    Service->>Pipeline: run(PipelineInput)
    Pipeline-->>Service: CritiqueResult
    Service-->>CLI: Present report path
    CLI-->>User: Display summary & location

    alt Single File Input
        CLI->>RepoFactory: select_repository(single file args)
        RepoFactory-->>Service: SingleFileContentRepository
    else Directory Input
        CLI->>RepoFactory: select_repository(directory args)
        RepoFactory-->>Service: DirectoryContentRepository
    end
```

## Dependency Validation

- The presentation layer terminates after creating a DTO and handing the request
to the application service.
- The application layer owns the `ContentRepository` interface and orchestrates
repository selection through dependency injection.
- Only infrastructure implementations touch the file system. They return pure
`PipelineInput` DTOs defined in the shared domain/application layer.
- The pipeline orchestrator consumes the DTO without awareness of where the
content originated.

This flow satisfies the dependency rule (`presentation → application → domain ←
infrastructure`) and avoids any shims between the CLI and repository
implementations.
