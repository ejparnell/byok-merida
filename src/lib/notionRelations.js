export function validateRelationTarget({
  property,
  configuredDatabase,
  configuredDatabaseId,
  expectedSyncedPropertyName,
}) {
  const errors = [];
  const warnings = [];
  const targetId = relationTargetId(property);
  const allowedTargetIds = relationAllowedTargetIds(configuredDatabase, configuredDatabaseId);

  if (targetId && !allowedTargetIds.has(targetId)) {
    if (property?.relation?.data_source_id && dataSourceIds(configuredDatabase).length === 0) {
      warnings.push("Notion returned a data_source_id for this relation; skipping strict database-id comparison.");
    } else {
      errors.push("relation target does not match the configured database.");
    }
  }

  const syncedPropertyName = property?.relation?.dual_property?.synced_property_name || "";
  if (syncedPropertyName && syncedPropertyName !== expectedSyncedPropertyName) {
    errors.push(`inverse relation must be named "${expectedSyncedPropertyName}", found "${syncedPropertyName}".`);
  }

  return { errors, warnings };
}

function relationTargetId(property) {
  return property?.relation?.database_id || property?.relation?.data_source_id || "";
}

function relationAllowedTargetIds(database, databaseId) {
  return new Set([
    databaseId,
    database?.id,
    ...dataSourceIds(database),
  ].filter(Boolean));
}

function dataSourceIds(database) {
  return (database?.data_sources || [])
    .map((dataSource) => dataSource?.id)
    .filter(Boolean);
}
