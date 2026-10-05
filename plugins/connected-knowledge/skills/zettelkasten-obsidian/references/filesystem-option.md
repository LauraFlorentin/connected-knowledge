# Optional Filesystem MCP

Use the focused [vault bridge](vault-bridge.md) for the normal connected-note
workflow. Offer Filesystem MCP when the user requests broader file management or
chooses an existing general file connection. This is a documented opt-in option;
Connected Knowledge does not install, bundle, register or activate it by default.

The upstream [Filesystem MCP server documentation](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)
describes a local Node.js server with file reading, writing, searching and moving
tools. Its access comes from selected command-line directories or client-provided
MCP Roots. Client Roots replace the command-line directory list; check the effective
scope with `list_allowed_directories` after connecting and whenever Roots change.
A selected folder is not a read-only permission: the server includes write tools.

## Set up the selected option

1. Reuse an existing Filesystem connection when it already has the user's intended
   scope. Inspect the actual host's connection configuration before changing it.
2. For a new connection, select the exact folders and a reviewed package version.
   A local stdio-capable host can use this connection fragment, after replacing
   both placeholders with the selected values:

   ```json
   {
     "command": "npx",
     "args": [
       "-y",
       "@modelcontextprotocol/server-filesystem@<reviewed-version>",
       "/absolute/user-selected/folder"
     ]
   }
   ```

   This is a fragment, not a universal host configuration file. Consult the current
   host setup instructions. Do not add it to the plugin manifests, reuse private
   tunnel credentials, or expose a new endpoint as part of choosing this option.
3. Inspect the effective allowed directories and test one harmless selected file.
   Limit access to the selected folders; do not use the home directory as a default.
4. Follow the existing guide, templates, source, identity and revision conventions.
   Preview requested changes and use existing task authorization; do not ask for
   redundant approval for an already authorized save. Verify actual saved files.

A general file tool does not itself supply Connected Knowledge's duplicate,
source-preservation or conflict handling. Those checks remain part of the assisted
workflow. The vault bridge has its own separately enabled save operation. Documenting this
optional server enables neither connection nor writer. If saving is requested
and no authorized write route is available, report the prepared result accurately.

Upstream behavior checked October 5, 2026. Native host setup and Filesystem save
trials have not been performed as part of the vault bridge milestone.
