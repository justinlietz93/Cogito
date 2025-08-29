import axios from 'axios';

// Base URLs for APIs
const ARXIV_API_URL = 'https://export.arxiv.org/api/query';
const WESTLAW_API_URL = '/api/westlaw'; // Proxy to backend which handles Westlaw API

// Backend API base (relative by default; can be overridden via env)
const BACKEND_BASE =
  process.env.REACT_APP_COGITO_API_BASE ||
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000');
const api = axios.create({ baseURL: BACKEND_BASE });

// --- Cogito Backend Integrations (Critique / Thesis / Enhancer) ---

/**
 * Run Critique Council pipeline via backend.
 * opts: {
 *   input_path?: string,
 *   ingest_batch?: boolean,
 *   scientific?: boolean,
 *   peer_review?: boolean,
 *   log_ingestion_choices?: boolean,
 *   pdf_backend?: "auto"|"pymupdf"|"pdfminer"|"pypdf2",
 *   ocr_enable?: boolean,
 *   ocr_lang?: string,
 *   tesseract_cmd?: string,
 *   audio_enable?: boolean,
 *   whisper_backend?: "whisper_local"|"whisper_openai",
 *   whisper_model?: string,
 *   latex?: boolean,
 *   latex_compile?: boolean,
 *   latex_output_dir?: string
 * }
 */
export const runCritique = async (opts = {}) => {
  try {
    const { data } = await api.post('/api/critique', opts);
    return data;
  } catch (error) {
    const msg = error?.response?.data || error?.message || 'Failed to execute critique';
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
};

/**
 * Run Thesis Builder via backend.
 * opts: { concept?: string, file?: string (dir or file), model?: string, force_fallback?: boolean, output_dir?: string }
 */
export const runThesis = async (opts = {}) => {
  try {
    const { data } = await api.post('/api/thesis', opts);
    return data;
  } catch (error) {
    const msg = error?.response?.data || error?.message || 'Failed to execute thesis builder';
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
};

/**
 * Run Research Enhancer via backend.
 * opts: { model?: string, force_fallback?: boolean }
 */
export const runEnhancer = async (opts = {}) => {
  try {
    const { data } = await api.post('/api/enhancer', opts);
    return data;
  } catch (error) {
    const msg = error?.response?.data || error?.message || 'Failed to execute research enhancer';
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
};

/**
 * Fetch recent results for UI listing.
 */
export const getResults = async () => {
  try {
    const { data } = await api.get('/api/results');
    return data;
  } catch (error) {
    const msg = error?.response?.data || error?.message || 'Failed to fetch results';
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
};

// --- ArXiv public API (unchanged dev helper) ---

// ArXiv API search function
export const searchArxiv = async (query, filters = {}) => {
  try {
    // Build search query with filters
    let searchQuery = query;
    
    if (filters.category) {
      searchQuery += ` AND cat:${filters.category}`;
    }
    
    if (filters.dateFrom) {
      // ArXiv doesn't directly support date filtering in the API
      // This would be handled in the results filtering
    }
    
    const params = {
      search_query: searchQuery,
      start: filters.start || 0,
      max_results: filters.maxResults || 20,
      sortBy: filters.sortBy || 'relevance',
      sortOrder: filters.sortOrder || 'descending'
    };
    
    const response = await axios.get(ARXIV_API_URL, { params });
    
    // Parse XML response
    // In a real implementation, we would use a proper XML parser
    // For this example, we'll simulate the parsed response
    
    // Simulate processing the XML response
    const results = simulateArxivResults(response.data, query);
    
    return results;
  } catch (error) {
    console.error('ArXiv API error:', error);
    throw new Error('Failed to search ArXiv');
  }
};

// Westlaw API search function (proxied through our backend)
export const searchWestlaw = async (query, filters = {}) => {
  try {
    // In a real implementation, this would call your backend API
    // which would then make the actual Westlaw API request
    
    // For this example, we'll simulate the response
    // Simulate a delay for the API call
    await new Promise(resolve => setTimeout(resolve, 800));
    
    // Simulate Westlaw results
    const results = simulateWestlawResults(query, filters);
    
    return results;
  } catch (error) {
    console.error('Westlaw API error:', error);
    throw new Error('Failed to search Westlaw');
  }
};

// Function to get document details
export const getDocument = async (id, source) => {
  try {
    // In a real implementation, this would call the appropriate API
    // based on the source (Westlaw or ArXiv)
    
    // For this example, we'll simulate the response
    await new Promise(resolve => setTimeout(resolve, 500));
    
    if (source === 'westlaw') {
      return simulateWestlawDocument(id);
    } else if (source === 'arxiv') {
      return simulateArxivDocument(id);
    } else {
      throw new Error('Invalid source');
    }
  } catch (error) {
    console.error('Document API error:', error);
    throw new Error('Failed to get document');
  }
};

// Function to get citation network
export const getCitationNetwork = async (documentId, source) => {
  try {
    // In a real implementation, this would call your backend API
    // which would retrieve citation data
    
    // For this example, we'll simulate the response
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    return simulateCitationNetwork(documentId, source);
  } catch (error) {
    console.error('Citation network API error:', error);
    throw new Error('Failed to get citation network');
  }
};

// Simulation functions for development/testing

function simulateArxivResults(xmlData, query) {
  // Simulate parsing XML and returning results
  const results = [];
  
  // Generate 5-10 random results
  const count = Math.floor(Math.random() * 6) + 5;
  
  for (let i = 0; i < count; i++) {
    results.push({
      id: `arxiv.${Date.now()}.${i}`,
      source: 'arxiv',
      title: `Research on ${query} - Scientific Perspective ${i + 1}`,
      authors: ['John Doe', 'Jane Smith'],
      date: new Date(Date.now() - Math.random() * 31536000000).toISOString().split('T')[0], // Random date within last year
      abstract: `This paper explores ${query} from a scientific perspective, examining the implications and applications in various fields.`,
      url: `https://arxiv.org/abs/2107.${10000 + i}`,
      relevance: Math.random() * 0.5 + 0.5, // Random relevance between 0.5 and 1.0
      categories: ['cs.AI', 'cs.CL'],
      citations: Math.floor(Math.random() * 100)
    });
  }
  
  return results;
}

function simulateWestlawResults(query, filters) {
  // Simulate Westlaw search results
  const results = [];
  
  // Generate 5-10 random results
  const count = Math.floor(Math.random() * 6) + 5;
  
  for (let i = 0; i < count; i++) {
    results.push({
      id: `westlaw.${Date.now()}.${i}`,
      source: 'westlaw',
      title: `Legal Analysis of ${query} - Case Study ${i + 1}`,
      court: ['Supreme Court', 'Circuit Court', 'District Court'][Math.floor(Math.random() * 3)],
      date: new Date(Date.now() - Math.random() * 31536000000).toISOString().split('T')[0], // Random date within last year
      summary: `This case examines the legal implications of ${query}, establishing precedent for future cases.`,
      url: `https://westlaw.com/document/${Date.now() + i}`,
      relevance: Math.random() * 0.5 + 0.5, // Random relevance between 0.5 and 1.0
      jurisdiction: ['Federal', 'State'][Math.floor(Math.random() * 2)],
      citations: Math.floor(Math.random() * 50)
    });
  }
  
  return results;
}

function simulateWestlawDocument(id) {
  // Simulate a Westlaw document
  return {
    id,
    source: 'westlaw',
    title: `Legal Analysis - Case Study ${id.split('.')[2]}`,
    court: 'Supreme Court',
    date: '2023-01-15',
    content: `
      <h1>Legal Analysis - Case Study</h1>
      <p>This is a simulated legal document from Westlaw.</p>
      <h2>Background</h2>
      <p>The case involves multiple parties disputing over intellectual property rights.</p>
      <h2>Legal Analysis</h2>
      <p>The court found that the defendant had infringed on the plaintiff's patent.</p>
      <h2>Conclusion</h2>
      <p>The court ruled in favor of the plaintiff, awarding damages of $1.2 million.</p>
    `,
    citations: [
      { id: 'westlaw.123456.1', title: 'Related Case 1' },
      { id: 'westlaw.123456.2', title: 'Related Case 2' }
    ],
    metadata: {
      jurisdiction: 'Federal',
      judges: ['John Roberts', 'Sonia Sotomayor'],
      keywords: ['patent', 'infringement', 'intellectual property']
    }
  };
}

function simulateArxivDocument(id) {
  // Simulate an ArXiv document
  return {
    id,
    source: 'arxiv',
    title: `Scientific Research Paper ${id.split('.')[2]}`,
    authors: ['John Doe', 'Jane Smith'],
    date: '2023-02-20',
    content: `
      <h1>Scientific Research Paper</h1>
      <p>This is a simulated scientific paper from ArXiv.</p>
      <h2>Abstract</h2>
      <p>We present a novel approach to machine learning that improves accuracy by 15%.</p>
      <h2>Methodology</h2>
      <p>Our approach combines neural networks with statistical analysis to achieve better results.</p>
      <h2>Results</h2>
      <p>Experiments show significant improvements over baseline methods.</p>
      <h2>Conclusion</h2>
      <p>The proposed method offers a promising direction for future research.</p>
    `,
    citations: [
      { id: 'arxiv.123456.1', title: 'Related Paper 1' },
      { id: 'arxiv.123456.2', title: 'Related Paper 2' }
    ],
    metadata: {
      categories: ['cs.AI', 'cs.CL'],
      keywords: ['machine learning', 'neural networks', 'artificial intelligence'],
      doi: '10.1234/5678.9012'
    }
  };
}

function simulateCitationNetwork(documentId, source) {
  // Simulate a citation network
  const nodes = [];
  const links = [];
  
  // Add the main document as the central node
  nodes.push({
    id: documentId,
    name: source === 'westlaw' ? 'Legal Document' : 'Scientific Paper',
    val: 20, // Size of the node
    color: source === 'westlaw' ? '#1a237e' : '#00796b'
  });
  
  // Generate 10-20 random nodes (cited documents)
  const count = Math.floor(Math.random() * 11) + 10;
  
  for (let i = 0; i < count; i++) {
    const nodeId = `${source}.citation.${i}`;
    const isOutgoing = Math.random() > 0.5; // Randomly decide if this is cited by or cites the main document
    
    nodes.push({
      id: nodeId,
      name: isOutgoing ? `Cited Document ${i + 1}` : `Citing Document ${i + 1}`,
      val: 10 + Math.random() * 10, // Random size between 10 and 20
      color: Math.random() > 0.3 ? 
        (source === 'westlaw' ? '#1a237e' : '#00796b') : // Same source
        (source === 'westlaw' ? '#00796b' : '#1a237e')   // Different source
    });
    
    // Add link
    links.push({
      source: isOutgoing ? documentId : nodeId,
      target: isOutgoing ? nodeId : documentId,
      value: Math.random() * 5 + 1 // Random link strength
    });
  }
  
  // Add some links between the other nodes
  const linkCount = Math.floor(count * 0.3); // Add about 30% as many inter-node links
  
  for (let i = 0; i < linkCount; i++) {
    const sourceIndex = Math.floor(Math.random() * count) + 1; // +1 to skip the main node
    let targetIndex = Math.floor(Math.random() * count) + 1;
    
    // Ensure source and target are different
    while (targetIndex === sourceIndex) {
      targetIndex = Math.floor(Math.random() * count) + 1;
    }
    
    links.push({
      source: nodes[sourceIndex].id,
      target: nodes[targetIndex].id,
      value: Math.random() * 3 + 1 // Random link strength, weaker than main links
    });
  }
  
  return { nodes, links };
}