/**
 * Redirect handler for legacy /project?path=... URLs
 * 
 * This load function intercepts the old URL format and redirects to the
 * new /project/[projectId] format using SvelteKit's native redirect.
 */

import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url, fetch }) => {
  const pathParam = url.searchParams.get('path');
  
  if (pathParam) {
    // Legacy URL detected - resolve to slug and redirect
    try {
      const response = await fetch('/api/project/slug', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: pathParam }),
      });
      
      if (response.ok) {
        const data = await response.json();
        const projectId = data.slug || data.projectId;
        
        if (projectId) {
          // Redirect to new format
          redirect(301, `/project/${projectId}`);
        }
      }
    } catch {
      // If slug lookup fails, redirect to home
      redirect(302, '/');
    }
    
    // Fallback: redirect to home if no slug found
    redirect(302, '/');
  }
  
  // No path param - redirect to home (this page shouldn't be accessed directly)
  redirect(302, '/');
};
