# Usage

`towncrier` is used for keeping track of the changelog. The relevant configuration aspects are:
- Each file can be formatted using reST
- The contents are rendered in bullets
- Each file should be labeled with the corresponding **pull request**, e.g. `NUM.TYPE.rst`
  + Where there is no clear corresponding pull request, `+` can be used instead of `NUM`

For mapping the types to headings, the following table can be used:


| **TYPE** | **Heading**                 |
| feat     | New Features                |
| api      | API Changes                 |
| bugfix   | Bug Fixes                   |
| misc     | Other Changes and Additions |

## Release


```bash
# View the changes
towncrier build --draft --version 0.6.2 --date "$(date -u +%Y-%m-%d)"
# Modify CHANGES.rst
towncrier build --version 0.6.3 --date "$(date -u +%Y-%m-%d)"
```
