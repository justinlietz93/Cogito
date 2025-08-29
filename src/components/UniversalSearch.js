import React, { useState, useEffect, useRef } from 'react';
import { 
  Paper, 
  InputBase, 
  IconButton, 
  Divider, 
  Menu, 
  MenuItem, 
  ListItemIcon, 
  ListItemText,
  Chip,
  Box
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Book as LegalIcon,
  Science as ScienceIcon,
  CalendarToday as DateIcon,
  Sort as SortIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useResearch } from '../contexts/ResearchContext';

function UniversalSearch() {
  const navigate = useNavigate();
  const { search } = useResearch();
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({
    sources: ['westlaw', 'arxiv'],
    dateRange: null,
    categories: []
  });
  const [activeFilters, setActiveFilters] = useState([]);
  const [anchorEl, setAnchorEl] = useState(null);
  const [filterType, setFilterType] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const searchTimeoutRef = useRef(null);
  const lastSearchRef = useRef('');

  // Reset isSearching state when component mounts or unmounts
  useEffect(() => {
    setIsSearching(false);
    return () => {
      setIsSearching(false);
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    
    // Don't search if query is empty or already searching
    if (!query.trim() || isSearching) {
      return;
    }
    
    // Don't search if the query is the same as the last search
    if (query.trim() === lastSearchRef.current) {
      return;
    }
    
    // Set searching state and save current query
    setIsSearching(true);
    lastSearchRef.current = query.trim();
    
    // Clear any existing timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    
    // Perform the search
    search(query, filters)
      .then(() => {
        navigate('/search', { state: { query, filters } });
        
        // Add a delay before allowing another search
        searchTimeoutRef.current = setTimeout(() => {
          setIsSearching(false);
        }, 1000);
      })
      .catch(() => {
        // Reset searching state after a delay even if there's an error
        searchTimeoutRef.current = setTimeout(() => {
          setIsSearching(false);
        }, 1000);
      });
  };

  const handleFilterClick = (event, type) => {
    setAnchorEl(event.currentTarget);
    setFilterType(type);
  };

  const handleFilterClose = () => {
    setAnchorEl(null);
    setFilterType(null);
  };

  const handleFilterChange = (type, value) => {
    let updatedFilters = { ...filters };
    
    switch (type) {
      case 'source':
        if (updatedFilters.sources.includes(value)) {
          updatedFilters.sources = updatedFilters.sources.filter(s => s !== value);
        } else {
          updatedFilters.sources = [...updatedFilters.sources, value];
        }
        break;
      case 'date':
        updatedFilters.dateRange = value;
        break;
      case 'category':
        if (updatedFilters.categories.includes(value)) {
          updatedFilters.categories = updatedFilters.categories.filter(c => c !== value);
        } else {
          updatedFilters.categories = [...updatedFilters.categories, value];
        }
        break;
      default:
        break;
    }
    
    setFilters(updatedFilters);
    updateActiveFilters(updatedFilters);
    handleFilterClose();
  };

  const updateActiveFilters = (updatedFilters) => {
    const active = [];
    
    // Source filters
    if (!updatedFilters.sources.includes('westlaw')) {
      active.push({ type: 'source', value: 'No Westlaw', key: 'no-westlaw' });
    }
    if (!updatedFilters.sources.includes('arxiv')) {
      active.push({ type: 'source', value: 'No ArXiv', key: 'no-arxiv' });
    }
    
    // Date filter
    if (updatedFilters.dateRange) {
      active.push({ 
        type: 'date', 
        value: `Since ${updatedFilters.dateRange}`, 
        key: `date-${updatedFilters.dateRange}` 
      });
    }
    
    // Category filters
    updatedFilters.categories.forEach(category => {
      active.push({ type: 'category', value: category, key: `category-${category}` });
    });
    
    setActiveFilters(active);
  };

  const removeFilter = (filterKey) => {
    const [type, value] = filterKey.split('-');
    let updatedFilters = { ...filters };
    
    switch (type) {
      case 'no':
        // Re-add the source that was filtered out
        updatedFilters.sources = [...updatedFilters.sources, value];
        break;
      case 'date':
        updatedFilters.dateRange = null;
        break;
      case 'category':
        updatedFilters.categories = updatedFilters.categories.filter(c => c !== value);
        break;
      default:
        break;
    }
    
    setFilters(updatedFilters);
    updateActiveFilters(updatedFilters);
  };

  return (
    <>
      <Paper
        component="form"
        onSubmit={handleSearch}
        sx={{ 
          p: '2px 4px', 
          display: 'flex', 
          alignItems: 'center', 
          width: '100%',
          borderRadius: 2
        }}
      >
        <IconButton sx={{ p: '10px' }} aria-label="search">
          <SearchIcon />
        </IconButton>
        <InputBase
          sx={{ ml: 1, flex: 1 }}
          placeholder="Search research sources (e.g., ArXiv; optional legal datasets)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={isSearching}
        />
        
        <IconButton 
          sx={{ p: '10px' }}
          aria-label="filter by source"
          onClick={(e) => handleFilterClick(e, 'source')}
          disabled={isSearching}
        >
          <FilterIcon />
        </IconButton>
        
        <Divider sx={{ height: 28, m: 0.5 }} orientation="vertical" />
        
        <IconButton 
          color="primary" 
          sx={{ p: '10px' }} 
          aria-label="search"
          onClick={handleSearch}
          disabled={isSearching || !query.trim()}
        >
          <SearchIcon />
        </IconButton>
      </Paper>
      
      {activeFilters.length > 0 && (
        <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {activeFilters.map((filter) => (
            <Chip
              key={filter.key}
              label={filter.value}
              onDelete={() => removeFilter(filter.key)}
              size="small"
              color={filter.type === 'source' ? 'primary' : (filter.type === 'date' ? 'secondary' : 'default')}
            />
          ))}
        </Box>
      )}
      
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleFilterClose}
      >
        {filterType === 'source' && (
          <>
            <MenuItem onClick={() => handleFilterChange('source', 'westlaw')}>
              <ListItemIcon>
                <LegalIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>
                Westlaw
              </ListItemText>
              {filters.sources.includes('westlaw') && '✓'}
            </MenuItem>
            <MenuItem onClick={() => handleFilterChange('source', 'arxiv')}>
              <ListItemIcon>
                <ScienceIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>
                ArXiv
              </ListItemText>
              {filters.sources.includes('arxiv') && '✓'}
            </MenuItem>
          </>
        )}
        
        {filterType === 'date' && (
          <>
            <MenuItem onClick={() => handleFilterChange('date', 'past-day')}>
              <ListItemIcon>
                <DateIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>
                Past 24 hours
              </ListItemText>
            </MenuItem>
            <MenuItem onClick={() => handleFilterChange('date', 'past-week')}>
              <ListItemIcon>
                <DateIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>
                Past week
              </ListItemText>
            </MenuItem>
            <MenuItem onClick={() => handleFilterChange('date', 'past-month')}>
              <ListItemIcon>
                <DateIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>
                Past month
              </ListItemText>
            </MenuItem>
            <MenuItem onClick={() => handleFilterChange('date', 'past-year')}>
              <ListItemIcon>
                <DateIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>
                Past year
              </ListItemText>
            </MenuItem>
          </>
        )}
        
        {filterType === 'category' && (
          <>
            <MenuItem onClick={() => handleFilterChange('category', 'constitutional-law')}>
              <ListItemText>
                Constitutional Law
              </ListItemText>
              {filters.categories.includes('constitutional-law') && '✓'}
            </MenuItem>
            <MenuItem onClick={() => handleFilterChange('category', 'intellectual-property')}>
              <ListItemText>
                Intellectual Property
              </ListItemText>
              {filters.categories.includes('intellectual-property') && '✓'}
            </MenuItem>
            <MenuItem onClick={() => handleFilterChange('category', 'cs.AI')}>
              <ListItemText>
                Computer Science - AI
              </ListItemText>
              {filters.categories.includes('cs.AI') && '✓'}
            </MenuItem>
            <MenuItem onClick={() => handleFilterChange('category', 'physics')}>
              <ListItemText>
                Physics
              </ListItemText>
              {filters.categories.includes('physics') && '✓'}
            </MenuItem>
          </>
        )}
      </Menu>
    </>
  );
}

export default UniversalSearch;