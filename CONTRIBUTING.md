# Contributing to Zendesk MCP Server

## Development Guidelines

### Git Workflow
- Make small, focused commits
- **ALWAYS use semantic commit messages** following the format: `<type>(<scope>): <subject>`
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
  - Scope: Optional, indicates area of change (e.g., `elt`, `auth`, `ssh`, `api`, `client`, `server`)
  - Subject: Brief description in present tense
  - Examples: 
    - `feat(api): add Redis caching`
    - `fix(auth): resolve automation button issue`
    - `docs(readme): update installation instructions`
    - `refactor(client): optimize data limits`
    - `feat(server): add full data access methods`
- Always commit before making major changes to existing files
- Use descriptive branch names for features: `feat/redis-caching`, `fix/auth-button`

### Semantic Commit Types

- **feat**: A new feature for the user
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **test**: Adding missing tests or correcting existing tests
- **chore**: Changes to the build process or auxiliary tools and libraries

### Scope Guidelines

For this Zendesk MCP Server project, common scopes include:
- `client`: Changes to zendesk_client.py
- `server`: Changes to server.py MCP interface
- `api`: Changes to API methods or endpoints
- `auth`: Authentication and authorization changes
- `data`: Data handling, limits, or processing changes
- `docs`: Documentation updates
- `config`: Configuration or setup changes
- `deps`: Dependency updates

### Examples of Good Commit Messages

```
feat(client): add ticket comment truncation limits
fix(server): resolve tool parameter validation
docs(examples): add full data access examples
refactor(api): optimize search result processing
chore(deps): update zenpy to latest version
test(client): add unit tests for comment methods
style(server): improve code formatting
```

### Code Quality

- Follow Python PEP 8 style guidelines
- Add type hints where appropriate
- Include docstrings for public methods
- Handle exceptions gracefully with informative error messages
- Test changes with actual Zendesk API before committing

### Pull Request Guidelines

- Create focused PRs that address a single concern
- Include tests for new functionality
- Update documentation as needed
- Use semantic commit messages in PR title
- Reference any related issues

### Development Setup

1. Clone the repository
2. Set up virtual environment: `python -m venv venv`
3. Activate environment: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -e .`
5. Set up environment variables in `.env` file
6. Test with: `uv run zendesk --help` 