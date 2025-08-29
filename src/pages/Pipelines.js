import React, { useMemo, useState } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  TextField,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Button,
  Divider,
  Snackbar,
  Alert,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';

/**
 * Starter GUI for running pipelines.
 * This is a front-end only foundation that:
 * - Lets you compose CLI commands for pipelines
 * - Copies the exact command to clipboard
 * - Outlines where a backend hook (/api/run) will be wired later
 *
 * Future wiring (backend):
 * - POST /api/run { command, cwd } -> streams run_critique.py or thesis/enhancer scripts
 * - GET /api/results -> list latest critique/syncretic outputs
 */
export default function Pipelines() {
  // Global info (front-end only; future API can hydrate this)
  const [projectRoot, setProjectRoot] = useState('Cogito'); // relative working dir for CLI
  const [primaryProvider, setPrimaryProvider] = useState('openrouter'); // informative only

  // Critique Council options
  const [inputPath, setInputPath] = useState('INPUT/');
  const [ingestBatch, setIngestBatch] = useState(true);
  const [scientific, setScientific] = useState(true);
  const [peerReview, setPeerReview] = useState(true);

  // Syncretic Catalyst - Thesis
  const [thesisConcept, setThesisConcept] = useState('Quantum computation applied to climate modeling');
  const [thesisModel, setThesisModel] = useState('openrouter'); // thesis supports: claude | deepseek | xai | openrouter

  // Syncretic Catalyst - Enhancer
  const [enhancerModel, setEnhancerModel] = useState('claude'); // enhancer supports: claude | deepseek

  // UX
  const [copied, setCopied] = useState(false);

  const critiqueCommand = useMemo(() => {
    const flags = [];
    if (ingestBatch) flags.push('--ingest-batch');
    if (scientific) flags.push('--scientific');
    if (peerReview) flags.push('--PR');

    const pathArg = inputPath && inputPath.trim().length > 0 ? inputPath.trim() : 'INPUT/';
    return `python run_critique.py ${pathArg} ${flags.join(' ')}`.trim();
  }, [inputPath, ingestBatch, scientific, peerReview]);

  const thesisCommand = useMemo(() => {
    const conceptArg = thesisConcept.replace(/"/g, '\\"');
    return `python src/syncretic_catalyst/thesis_builder.py "${conceptArg}" --model ${thesisModel}`;
  }, [thesisConcept, thesisModel]);

  const enhancerCommand = useMemo(() => {
    return `python src/syncretic_catalyst/research_enhancer.py --model ${enhancerModel}`;
  }, [enhancerModel]);

  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Pipelines
      </Typography>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        This starter GUI generates exact CLI commands for your pipelines. Copy and run them in a terminal at the project root.
        Backend execution hooks and results listing are intentionally left as stubs to be wired later.
      </Typography>

      <Grid container spacing={3}>
        {/* Environment Overview */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, borderRadius: 2 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Project Root (cwd)"
                helperText="Relative working dir where you run commands"
                value={projectRoot}
                onChange={(e) => setProjectRoot(e.target.value)}
                size="small"
                sx={{ minWidth: 260 }}
              />
              <TextField
                label="Primary Provider (informational)"
                helperText="Matches config.yaml api.primary_provider"
                value={primaryProvider}
                onChange={(e) => setPrimaryProvider(e.target.value)}
                size="small"
                sx={{ minWidth: 260 }}
              />
            </Stack>
          </Paper>
        </Grid>

        {/* Critique Council */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 2 }}>
            <Typography variant="h6" gutterBottom>
              Critique Council
            </Typography>

            <Stack spacing={2}>
              <TextField
                label="Input Path"
                value={inputPath}
                onChange={(e) => setInputPath(e.target.value)}
                helperText="File or directory. Defaults to INPUT/"
                fullWidth
              />

              <FormGroup>
                <FormControlLabel
                  control={<Checkbox checked={ingestBatch} onChange={(e) => setIngestBatch(e.target.checked)} />}
                  label="Batch Ingest (concatenate INPUT/ files)"
                />
                <FormControlLabel
                  control={<Checkbox checked={scientific} onChange={(e) => setScientific(e.target.checked)} />}
                  label="Scientific Mode (use scientific methodology agents)"
                />
                <FormControlLabel
                  control={<Checkbox checked={peerReview} onChange={(e) => setPeerReview(e.target.checked)} />}
                  label="Peer Review (PR) mode"
                />
              </FormGroup>

              <Divider />

              <CommandPreview
                title="Critique Command"
                command={critiqueCommand}
                onCopy={() => copy(critiqueCommand)}
                instructions={[
                  `cd ${projectRoot}`,
                  critiqueCommand,
                ]}
              />
            </Stack>
          </Paper>
        </Grid>

        {/* Syncretic Catalyst - Thesis */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 2 }}>
            <Typography variant="h6" gutterBottom>
              Syncretic Catalyst — Thesis Builder
            </Typography>

            <Stack spacing={2}>
              <TextField
                label="Concept / Hypothesis"
                value={thesisConcept}
                onChange={(e) => setThesisConcept(e.target.value)}
                multiline
                minRows={3}
                helperText="Enter your research concept"
                fullWidth
              />

              <FormControl size="small" sx={{ minWidth: 220 }}>
                <InputLabel>Model</InputLabel>
                <Select
                  label="Model"
                  value={thesisModel}
                  onChange={(e) => setThesisModel(e.target.value)}
                >
                  <MenuItem value="claude">claude</MenuItem>
                  <MenuItem value="deepseek">deepseek</MenuItem>
                  <MenuItem value="xai">xai</MenuItem>
                  <MenuItem value="openrouter">openrouter</MenuItem>
                </Select>
              </FormControl>

              <Divider />

              <CommandPreview
                title="Thesis Command"
                command={thesisCommand}
                onCopy={() => copy(thesisCommand)}
                instructions={[
                  `cd ${projectRoot}`,
                  thesisCommand,
                ]}
              />

              <Alert severity="info" variant="outlined">
                Output will be saved under syncretic_output/ with timestamped files (papers_*.json/md, agent_*.md, thesis_*.md, research_report_*.md).
              </Alert>
            </Stack>
          </Paper>
        </Grid>

        {/* Syncretic Catalyst - Research Enhancer */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 2 }}>
            <Typography variant="h6" gutterBottom>
              Syncretic Catalyst — Research Enhancer
            </Typography>

            <Stack spacing={2}>
              <FormControl size="small" sx={{ minWidth: 220 }}>
                <InputLabel>Model</InputLabel>
                <Select
                  label="Model"
                  value={enhancerModel}
                  onChange={(e) => setEnhancerModel(e.target.value)}
                >
                  <MenuItem value="claude">claude</MenuItem>
                  <MenuItem value="deepseek">deepseek</MenuItem>
                </Select>
              </FormControl>

              <Divider />

              <CommandPreview
                title="Enhancer Command"
                command={enhancerCommand}
                onCopy={() => copy(enhancerCommand)}
                instructions={[
                  `cd ${projectRoot}`,
                  enhancerCommand,
                ]}
              />

              <Alert severity="info" variant="outlined">
                Documents should be placed in src/syncretic_catalyst/workspaces/some_project/doc. Results will be written under output_results/syncretic_catalyst/some_project.
              </Alert>
            </Stack>
          </Paper>
        </Grid>

        {/* Backend wiring note */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, borderRadius: 2 }}>
            <Typography variant="subtitle1" gutterBottom>Backend Execution (Future)</Typography>
            <Typography variant="body2" color="text.secondary">
              To run pipelines from the browser without copying commands, add a small local server with a POST /api/run endpoint
              that executes commands in the project root (cwd). Replace the copy buttons with a call to that endpoint.
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      <Snackbar
        open={copied}
        autoHideDuration={2000}
        onClose={() => setCopied(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity="success" onClose={() => setCopied(false)} variant="filled">
          Command copied to clipboard
        </Alert>
      </Snackbar>
    </Box>
  );
}

function CommandPreview({ title, command, onCopy, instructions = [] }) {
  return (
    <Box>
      <Typography variant="subtitle1" gutterBottom>{title}</Typography>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: '#0b1324' }}>
        <Box component="pre" sx={{ m: 0, color: '#cfe3ff', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {command}
        </Box>
      </Paper>

      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
        <Button variant="contained" onClick={onCopy}>Copy Command</Button>
      </Stack>

      {instructions.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary" gutterBottom>Manual steps</Typography>
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Box component="pre" sx={{ m: 0, whiteSpace: 'pre-wrap' }}>
              {instructions.join('\n')}
            </Box>
          </Paper>
        </Box>
      )}
    </Box>
  );
}