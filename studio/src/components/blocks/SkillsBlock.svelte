<!--
  SkillsBlock.svelte — Quick access to lens skills (RFC-086)

  Shows available skills from active lens with shortcuts.
  Click to execute on current document.
-->
<script lang="ts">
  import {
    writerState,
    executeSkill,
    type LensSkill,
  } from '../../stores';

  // Use LensSkill as Skill
  type Skill = LensSkill;

  interface Props {
    /** Override values (optional - uses writer store by default) */
    skills?: Skill[];
    recentSkills?: string[];
    lensName?: string;
    onExecute?: (skillId: string) => void;
    onConfigure?: (skillId: string) => void;
  }

  let {
    skills: propSkills,
    recentSkills: propRecentSkills,
    lensName: propLensName,
    onExecute,
    onConfigure,
  }: Props = $props();

  // Use props if provided, otherwise use writer store
  const skills = $derived(propSkills ?? writerState.lensSkills);
  const recentSkills = $derived(propRecentSkills ?? writerState.recentSkills);
  const lensName = $derived(propLensName ?? writerState.lensName);

  function handleExecute(skillId: string) {
    if (onExecute) {
      onExecute(skillId);
    } else {
      executeSkill(skillId);
    }
  }

  let collapsed = $state(false);

  const groupedSkills = $derived(() => {
    const groups: Record<string, Skill[]> = {};
    for (const skill of skills) {
      if (!groups[skill.category]) groups[skill.category] = [];
      groups[skill.category].push(skill);
    }
    return groups;
  });

  const recent = $derived(
    recentSkills
      .map((id) => skills.find((s) => s.id === id))
      .filter(Boolean)
      .slice(0, 3) as Skill[]
  );

  const categoryLabels: Record<string, string> = {
    validation: '🔍 Validation',
    creation: '✏️ Creation',
    transformation: '🔧 Transformation',
    utility: '⚙️ Utility',
  };

  function handleSkillClick(skill: Skill) {
    handleExecute(skill.id);
  }
</script>

<div class="skills-block" class:collapsed>
  <button class="header" onclick={() => (collapsed = !collapsed)}>
    <span class="title">🛠️ Skills</span>
    <span class="lens-name">{lensName}</span>
    <span class="count">{skills.length}</span>
    <span class="toggle">{collapsed ? '▶' : '▼'}</span>
  </button>

  {#if !collapsed}
    <div class="content">
      {#if recent.length > 0}
        <div class="recent-section">
          <span class="label">Recent:</span>
          <div class="recent-skills">
            {#each recent as skill}
              <button
                class="skill-chip"
                onclick={() => handleSkillClick(skill)}
                title={skill.description}
              >
                {skill.name}
              </button>
            {/each}
          </div>
        </div>
      {/if}

      <div class="categories">
        {#each Object.entries(groupedSkills()) as [category, categorySkills]}
          <div class="category">
            <div class="category-name">{categoryLabels[category] || category}</div>
            <div class="category-skills">
              {#each categorySkills as skill}
                <button
                  class="skill-row"
                  onclick={() => handleSkillClick(skill)}
                  title={skill.description}
                >
                  <span class="shortcut">{skill.shortcut}</span>
                  <span class="name">{skill.name}</span>
                </button>
              {/each}
            </div>
          </div>
        {/each}
      </div>

      {#if skills.length === 0}
        <div class="empty">No skills available for this lens</div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .skills-block {
    background: var(--surface-2, #1a1a2e);
    border-radius: 8px;
    overflow: hidden;
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 12px;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--surface-3, #252547);
    cursor: pointer;
    border: none;
    width: 100%;
    text-align: left;
    color: inherit;
  }

  .header:hover {
    background: var(--surface-4, #2d2d5a);
  }

  .title {
    font-weight: 600;
  }

  .lens-name {
    flex: 1;
    color: var(--text-muted, #888);
    font-size: 10px;
  }

  .count {
    background: var(--surface-1, #0f0f1a);
    padding: 2px 6px;
    border-radius: 10px;
    font-size: 10px;
    color: var(--text-muted, #888);
  }

  .toggle {
    color: var(--text-muted, #888);
    font-size: 10px;
  }

  .content {
    padding: 8px;
  }

  .recent-section {
    padding-bottom: 8px;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--border, #333);
  }

  .label {
    color: var(--text-muted, #888);
    font-size: 10px;
    margin-bottom: 4px;
    display: block;
  }

  .recent-skills {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .skill-chip {
    background: var(--accent, #6366f1);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 4px 10px;
    font-size: 11px;
    cursor: pointer;
    font-family: inherit;
  }

  .skill-chip:hover {
    background: var(--accent-hover, #4f46e5);
  }

  .categories {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .category {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .category-name {
    font-size: 10px;
    color: var(--text-muted, #888);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .category-skills {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .skill-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    border: none;
    background: transparent;
    text-align: left;
    color: inherit;
    width: 100%;
  }

  .skill-row:hover {
    background: var(--surface-3, #252547);
  }

  .shortcut {
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    color: var(--accent, #6366f1);
    min-width: 48px;
    font-size: 11px;
  }

  .name {
    color: var(--text, #fff);
  }

  .empty {
    padding: 16px;
    text-align: center;
    color: var(--text-muted, #888);
  }
</style>
