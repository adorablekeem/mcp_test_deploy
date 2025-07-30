# Contributing to scalapay-mcp-kam

The following is a contribution guide for the project. To maintain the quality and consistency of our codebase, we ask that all contributors follow these guidelines.

## Making Changes

- **Pull Requests**: All changes to the project should be made through Pull Requests (PRs). Direct commits to the main branch are discouraged to ensure every change is reviewed and tested.

## Commit Messages

- **Conventional Commits**: We follow the [Conventional Commits standard](https://www.conventionalcommits.org/en/v1.0.0/). This standard provides an easy set of rules for creating an explicit commit history, making it easier to write automated tools on top of. You can use the `commitizen` CLI tool by running `cz commit` to help you write commit messages that adhere to this standard.

## Pull Requests

- **Builds Must Pass**: Ensure that your PR builds are passing before you assign reviewers. This includes passing all tests, lints, and any other checks that are part of the continuous integration process.
- **Reviewers**: PRs should be reviewed by the code owner(s) and any other involved parties. Make sure to assign them as reviewers when you create your PR.
- **Code Style**: We enforce code style and quality through linting and formatting checks. Use the provided Make targets (`make lint`, `make fmt`, `make check`) to check your code style and format your code before pushing your commits.
- **Issue Linking**: Our issue management is done through YouTrack. Changes proposed in a PR should be linked to an issue in YouTrack. Ensure you mention the related issue in your PR title.
- **Size of PRs**: PRs should contain a single unit of work to keep the review process manageable. Large PRs are hard to review and understand, so break down large features or changes into smaller, manageable pieces.

## Project Versioning

- **Versioning Standards**: We follow specific standards for project versioning. For details on versioning, refer to the contribution guide available on our Confluence page: [Project Versioning and Release Management](<insert-our-link-to-confluence-here>).
