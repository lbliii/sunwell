/**
 * Redirect handler for legacy /writer?path=... URLs
 */

import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url, fetch }) => {
  const pathParam = url.searchParams.get('path');
  
  if (pathParam) {
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
          // Preserve other query params (file, lens)
          const newUrl = new URL(`/project/${projectId}/writer`, url.origin);
          const file = url.searchParams.get('file');
          const lens = url.searchParams.get('lens');
          if (file) newUrl.searchParams.set('file', file);
          if (lens) newUrl.searchParams.set('lens', lens);
          
          redirect(301, newUrl.pathname + newUrl.search);
        }
      }
    } catch {
      redirect(302, '/');
    }
    
    redirect(302, '/');
  }
  
  redirect(302, '/');
};
