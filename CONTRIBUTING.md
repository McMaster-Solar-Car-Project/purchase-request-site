# Contributing to Purchase Request Site

Thank you for your interest in contributing to the Purchase Request Site! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Code Style and Standards](#code-style-and-standards)
- [Testing](#testing)
- [Deployment](#deployment)
- [Long-term Maintenance](#long-term-maintenance)

## Code of Conduct

This project is part of the McMaster Solar Car Project. Please be respectful, inclusive, and collaborative in all interactions. We expect all contributors to follow our community guidelines.

## Getting Started

### Prerequisites

- **Operating System**: macOS or WSL (Windows users should use WSL)
- **Package Manager**: Homebrew (install via [brew.sh](https://brew.sh/))
- **Python**: 3.11 (managed via uv)
- **Git**: For version control

### Required Tools

Install the following system dependencies:

```bash
brew install uv gitleaks lefthook ruff
```

## Development Setup

### 1. Fork and Clone the Repository

```bash
# Fork the repository on GitHub, then clone your fork
git clone git@github.com:YOUR_USERNAME/purchase-request-site.git
cd purchase-request-site

# Add the upstream repository
git remote add upstream git@github.com:McMaster-Solar-Car-Project/purchase-request-site.git
```

### 2. Environment Setup

```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Install project dependencies
uv sync

# Install git hooks (required for development)
lefthook install
```

### 3. Environment Variables

**Important**: Contact Raj for the required environment variables before running the application. 

### 4. Run the Application

```bash
# Start the development server
uv run run.py
```

The application will be available at `http://localhost:8000` (or the port specified in your configuration).

## Making Changes

### 1. Create a Feature Branch

```bash
# Ensure you're on the main branch and it's up to date
git checkout main
git pull upstream main

# Create a new feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Your Changes

- Write clean, readable code
- Follow the existing code style and patterns
- Add comments for complex logic
- Update documentation if necessary

### 3. Test Your Changes

```bash
# Run the application locally to test your changes
uv run run.py

# Test all functionality that your changes affect
```

### 4. Commit Your Changes

```bash
# Stage your changes
git add .

# Commit with a descriptive message
git commit -m "Add: brief description of your changes"
```

**Commit Message Guidelines:**
- Use the format: `Name/Description`
- Keep descriptions concise but descriptive seperated with dashes

## Pull Request Process

### 1. Push Your Changes

```bash
# Push your feature branch to your fork
git push origin feature/your-feature-name
```

### 2. Create a Pull Request

1. Go to the [GitHub repository](https://github.com/McMaster-Solar-Car-Project/purchase-request-site)
2. Click "New Pull Request"
3. Select your feature branch
4. Fill out the PR template with:
   - Description of changes
   - Link to the Github Issue
   - Screenshots (if applicable)


### 3. Staging Environment

Staging environment is currently broken, test locally, will be fixed soon.

### 4. Review Process

- Address all review comments
- Ensure all checks pass (Linting, Formatting, Gitleaks)
- Test the staging environment thoroughly

## Code Style and Standards

### Python Code Style

This project uses **Ruff** for linting and formatting. The configuration is defined in `pyproject.toml`.

**Running Linting:**
```bash
# Check for issues
ruff check

# Auto-fix issues
ruff check --fix

# Format code
ruff format
```

### Git Hooks

The project uses Lefthook for git hooks. These run automatically on commit:

- **Pre-commit hooks:**
  - Prevents direct commits to main branch
  - Runs Ruff linting and formatting
  - Scans for secrets with Gitleaks


## Testing

We need testing pipelines really badly, everything is manual right now.

## Deployment

### Production Environment

- **Platform**: Digital Ocean
- **Deployment**: Automatic via GitHub Actions
- **Database**: Supabase

## Opening GitHub Issues

### Bug Reports

You can open bug reports autonomously. When creating a bug report, please include:

- **Clear description** of the bug
- **Steps to reproduce** the issue
- **Expected behavior** vs actual behavior
- **Screenshots** (especially for UI bugs or when the bug is hard to replicate)
- **Environment details** (browser, OS, etc.)

**Template for bug reports:**
```
**Bug Description:**
[Clear description of what's wrong]

**Steps to Reproduce:**
1. Go to...
2. Click on...
3. See error...

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]

**Screenshots:**
[If applicable]

**Environment:**
- Browser: [e.g., Chrome 120]
- OS: [e.g., macOS 14.0]
```

### Feature Requests and Suggestions

For new features or suggestions:

1. **Discuss first**: Bring up the idea in team chat or during meetings
2. **Get team feedback**: Ensure it's a good idea worth exploring
3. **Open formal issue**: Once approved, create a GitHub issue to formalize the request

**Template for feature requests:**
```
**Feature Description:**
[Clear description of the proposed feature]

**Problem it solves:**
[What problem does this address?]

**Proposed solution:**
[How should this be implemented?]

**Additional context:**
[Any other relevant information]
```

## Getting Help

- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Discussions**: Use GitHub Discussions for questions and general discussion
- **Contact**: Reach out to Raj for environment variables or urgent issues

## License

This project is part of the McMaster Solar Car Project. Please ensure you have the appropriate permissions before contributing.

---

Thank you for contributing to the Purchase Request Site! Your contributions help make this project better for the entire McMaster Solar Car team.
