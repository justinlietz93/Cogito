import React from 'react';
import { 
  Box, 
  Grid, 
  Paper, 
  Typography, 
  Button, 
  List, 
  ListItem, 
  ListItemText, 
  ListItemSecondaryAction, 
  IconButton,
  Divider,
  Card,
  CardContent,
  CardActions
} from '@mui/material';
import {
  Search as SearchIcon,
  Visibility as ViewIcon,
  RateReview as ReviewIcon,
  TrendingUp as TrendingIcon,
  Bookmark as BookmarkIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useResearch } from '../contexts/ResearchContext';
import DocumentCard from '../components/DocumentCard';

function Dashboard() {
  const navigate = useNavigate();
  const { recentDocuments, savedDocuments } = useResearch();

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      
      <Grid container spacing={3}>
        {/* Quick Search Card */}
        <Grid item xs={12} md={6}>
          <Card sx={{ borderRadius: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Search
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Search across scientific sources (e.g., ArXiv) and optional legal datasets to find relevant documents.
              </Typography>
            </CardContent>
            <CardActions sx={{ p: 2, pt: 0 }}>
              <Button 
                variant="contained" 
                color="primary" 
                startIcon={<SearchIcon />}
                onClick={() => navigate('/search')}
              >
                Start New Search
              </Button>
            </CardActions>
          </Card>
        </Grid>
        
        {/* Peer Review Card */}
        <Grid item xs={12} md={6}>
          <Card sx={{ borderRadius: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Peer Review
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Manage your peer review assignments and submissions.
              </Typography>
            </CardContent>
            <CardActions sx={{ p: 2, pt: 0 }}>
              <Button 
                variant="outlined" 
                color="primary" 
                startIcon={<ReviewIcon />}
                onClick={() => navigate('/peer-review')}
              >
                View Peer Reviews
              </Button>
            </CardActions>
          </Card>
        </Grid>
        
        {/* Recent Documents */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Recent Documents
              </Typography>
              <Button 
                size="small" 
                endIcon={<ViewIcon />}
                onClick={() => navigate('/document/recent')}
              >
                View All
              </Button>
            </Box>
            
            {recentDocuments.length > 0 ? (
              <List>
                {recentDocuments.slice(0, 5).map((document, index) => (
                  <React.Fragment key={document.id}>
                    {index > 0 && <Divider />}
                    <ListItem button onClick={() => navigate(`/document/${document.id}`)}>
                      <ListItemText
                        primary={document.title}
                        secondary={`${document.source === 'westlaw' ? 'Legal' : 'Scientific'} • ${document.date}`}
                      />
                      <ListItemSecondaryAction>
                        <IconButton edge="end" onClick={() => navigate(`/document/${document.id}`)}>
                          <ViewIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  </React.Fragment>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No recent documents. Start searching to find documents.
              </Typography>
            )}
          </Paper>
        </Grid>
        
        {/* Saved Documents */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Saved Documents
              </Typography>
              <Button 
                size="small" 
                endIcon={<BookmarkIcon />}
                onClick={() => navigate('/document/saved')}
              >
                View All
              </Button>
            </Box>
            
            {savedDocuments.length > 0 ? (
              <List>
                {savedDocuments.slice(0, 5).map((document, index) => (
                  <React.Fragment key={document.id}>
                    {index > 0 && <Divider />}
                    <ListItem button onClick={() => navigate(`/document/${document.id}`)}>
                      <ListItemText
                        primary={document.title}
                        secondary={`${document.source === 'westlaw' ? 'Legal' : 'Scientific'} • ${document.date}`}
                      />
                      <ListItemSecondaryAction>
                        <IconButton edge="end" onClick={() => navigate(`/document/${document.id}`)}>
                          <ViewIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  </React.Fragment>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No saved documents. Save documents to access them quickly.
              </Typography>
            )}
          </Paper>
        </Grid>
        
        {/* Trending Research */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, borderRadius: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <TrendingIcon sx={{ mr: 1 }} color="primary" />
              <Typography variant="h6">
                Trending Research Topics
              </Typography>
            </Box>
            
            <Grid container spacing={2}>
              {['AI and Legal Ethics', 'Patent Law in Biotechnology', 'Climate Change Litigation', 'Data Privacy Regulations'].map((topic) => (
                <Grid item xs={12} sm={6} md={3} key={topic}>
                  <Card variant="outlined" sx={{ borderRadius: 2 }}>
                    <CardContent>
                      <Typography variant="subtitle1">{topic}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        Trending across research domains
                      </Typography>
                    </CardContent>
                    <CardActions>
                      <Button size="small" onClick={() => navigate('/search', { state: { query: topic } })}>
                        Explore
                      </Button>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Paper>
        </Grid>
        
        {/* Featured Document */}
        {recentDocuments.length > 0 && (
          <Grid item xs={12}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Featured Document
              </Typography>
              <DocumentCard document={recentDocuments[0]} saved={savedDocuments.some(d => d.id === recentDocuments[0].id)} />
            </Box>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

export default Dashboard;