<!--
  ContactsBlock — Contact cards with quick actions (RFC-080)
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface Contact {
		id: string;
		name: string;
		email?: string;
		phone?: string;
		avatar?: string;
		tags?: string[];
	}

	interface Props {
		data: {
			contacts: Contact[];
			contact_count: number;
			all_tags?: string[];
		};
		onAction?: (actionId: string, contactId?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function getInitials(name: string): string {
		return name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
	}

	function handleCall(contactId: string) { onAction?.('call', contactId); }
	function handleMessage(contactId: string) { onAction?.('message', contactId); }
	function handleEmail(contactId: string) { onAction?.('email', contactId); }
</script>

<div class="contacts-view">
	<header class="contacts-header">
		<h3 class="contacts-title">Contacts</h3>
		<span class="contacts-count">{data.contact_count} total</span>
	</header>

	{#if data.contacts.length > 0}
		<div class="contact-list">
			{#each data.contacts.slice(0, 6) as contact, i (contact.id)}
				<div class="contact-card" in:fly={{ y: 15, delay: staggerDelay(i), duration: 250 }}>
					<div class="avatar" aria-hidden="true">{contact.avatar || getInitials(contact.name)}</div>
					<div class="contact-info">
						<span class="contact-name">{contact.name}</span>
						{#if contact.email}
							<span class="contact-email">{contact.email}</span>
						{/if}
					</div>
					<div class="contact-actions">
						{#if contact.phone}
							<button class="action-icon" onclick={() => handleCall(contact.id)} aria-label="Call {contact.name}">📞</button>
						{/if}
						<button class="action-icon" onclick={() => handleMessage(contact.id)} aria-label="Message {contact.name}">💬</button>
						{#if contact.email}
							<button class="action-icon" onclick={() => handleEmail(contact.id)} aria-label="Email {contact.name}">✉️</button>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="empty-state"><p>No contacts found</p></div>
	{/if}
</div>

<style>
	.contacts-view { display: flex; flex-direction: column; gap: var(--space-4, 16px); }
	.contacts-header { display: flex; justify-content: space-between; align-items: center; }
	.contacts-title { margin: 0; font-size: var(--text-lg, 18px); font-weight: 600; color: var(--text-primary, #fff); }
	.contacts-count { color: var(--text-tertiary, #666); font-size: var(--text-sm, 14px); }
	.contact-list { display: flex; flex-direction: column; gap: var(--space-2, 8px); }
	.contact-card {
		display: flex; align-items: center; gap: var(--space-3, 12px);
		padding: var(--space-3, 12px); background: var(--bg-primary, #0a0a0a);
		border-radius: var(--radius-md, 8px); transition: all 0.2s ease;
	}
	.contact-card:hover { background: rgba(255, 215, 0, 0.05); }
	.avatar {
		width: 40px; height: 40px; border-radius: 50%;
		background: linear-gradient(135deg, rgba(255, 215, 0, 0.2), rgba(255, 215, 0, 0.1));
		color: var(--gold, #ffd700); display: flex; align-items: center; justify-content: center;
		font-weight: 600; font-size: var(--text-sm, 14px); flex-shrink: 0;
	}
	.contact-info { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
	.contact-name { color: var(--text-primary, #fff); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.contact-email { color: var(--text-tertiary, #666); font-size: var(--text-xs, 12px); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.contact-actions { display: flex; gap: var(--space-1, 4px); }
	.action-icon {
		background: none; border: none; cursor: pointer; padding: var(--space-1, 4px);
		border-radius: var(--radius-sm, 4px); transition: all 0.15s ease; font-size: var(--text-base, 16px);
	}
	.action-icon:hover { background: rgba(255, 215, 0, 0.1); }
	.action-icon:focus-visible { outline: 2px solid var(--gold, #ffd700); outline-offset: 2px; }
	.empty-state { text-align: center; padding: var(--space-6, 24px); color: var(--text-tertiary, #666); }
</style>
