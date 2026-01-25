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

  // O(1) skill lookup index
  const skillsById = $derived(new Map(skills.map(s => [s.id, s])));

  // Group skills by category in a single pass
  const groupedSkills = $derived.by(() => {
    const groups: Record<string, Skill[]> = {};
    for (const skill of skills) {
      if (!groups[skill.category]) groups[skill.category] = [];
      groups[skill.category].push(skill);
    }
    return groups;
  });

  // Use Map for O(1) lookups instead of O(n) find
  const recent = $derived(
    recentSkills
      .map((id) => skillsById.get(id))
      .filter((s): s is Skill => s !== undefined)
      .slice(0, 3)
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
            {#each recent as skill (skill.id)}
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
        {#each Object.entries(groupedSkills) as [category, categorySkills] (category)}
          <div class="category">
            <div class="category-name">{categoryLabels[category] || category}</div>
            <div class="category-skills">
              {#each categorySkills as skill (skill.id)}
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
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    overflow: hidden;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    cursor: pointer;
    border: none;
    width: 100%;
    text-align: left;
    color: inherit;
    transition: background var(--transition-fast);
  }

  .header:hover {
    background: var(--accent-hover);
  }

  .title {
    font-weight: 600;
  }

  .lens-name {
    flex: 1;
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }

  .count {
    background: var(--bg-primary);
    padding: var(--space-px) var(--space-1);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }

  .toggle {
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }

  .content {
    padding: var(--space-2);
  }

  .recent-section {
    padding-bottom: var(--space-2);
    margin-bottom: var(--space-2);
    border-bottom: 1px solid var(--border-subtle);
  }

  .label {
    color: var(--text-secondary);
    font-size: var(--text-xs);
    margin-bottom: var(--space-1);
    display: block;
  }

  .recent-skills {
    display: flex;
    gap: var(--space-1);
    flex-wrap: wrap;
  }

  .skill-chip {
    background: var(--ui-gold);
    color: var(--bg-primary);
    border: none;
    border-radius: var(--radius-full);
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    cursor: pointer;
    font-family: inherit;
    transition: background var(--transition-fast);
  }

  .skill-chip:hover {
    background: var(--ui-gold-soft);
  }

  .categories {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .category {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .category-name {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .category-skills {
    display: flex;
    flex-direction: column;
    gap: var(--space-px);
  }

  .skill-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    cursor: pointer;
    border: none;
    background: transparent;
    text-align: left;
    color: inherit;
    width: 100%;
    transition: background var(--transition-fast);
  }

  .skill-row:hover {
    background: var(--bg-tertiary);
  }

  .shortcut {
    font-family: var(--font-mono);
    color: var(--text-gold);
    min-width: 48px;
    font-size: var(--text-xs);
  }

  .name {
    color: var(--text-primary);
  }

  .empty {
    padding: var(--space-4);
    text-align: center;
    color: var(--text-secondary);
  }
</style>
